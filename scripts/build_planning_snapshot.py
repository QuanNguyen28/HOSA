"""Build v0.3.0 availability metrics from immutable v0.2.0 visibility intervals."""
import argparse
from bisect import bisect_left, bisect_right
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.planning.metrics import assess, assess_soft
from app.planning.models import Constraints, utc
from app.services.lunarsight.durations import bounds


def read(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root=ROOT):
    source = root/"data/processed/lunarsight/v0.2.0"
    target = root/"data/processed/lunarsight/v0.3.0"
    scenario_path = root/"manifests/lunarsight/config/scenario.json"
    scenario = json.loads(scenario_path.read_text())
    preferences = Constraints.model_validate(scenario["example_constraints"])
    requirements = scenario["example_requirements"]
    inputs, outputs = {}, {}
    for subdir in ("horizon", "ephemeris"):
        for path in sorted((source/subdir).glob("*.csv")):
            destination = target/subdir/path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            inputs[path.relative_to(root).as_posix()] = checksum(path)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source/"site_catalog.geojson", target/"site_catalog.geojson")
    inputs[(source/"site_catalog.geojson").relative_to(root).as_posix()] = checksum(source/"site_catalog.geojson")
    inputs[scenario_path.relative_to(root).as_posix()] = checksum(scenario_path)
    for prefix in ("Site01", "Site04"):
        path = source/"visibility"/f"{prefix}_intervals.csv"
        rows = read(path)
        starts, ends = [[utc(r[key]) for r in rows] for key in ("start_utc", "end_utc")]
        if any(b <= a for a, b in zip(starts, ends)) or starts[1:] != ends[:-1]:
            raise ValueError("Visibility intervals must be ordered, contiguous and positive")
        inputs[path.relative_to(root).as_posix()] = checksum(path)
        outdir = target/"visibility"
        outdir.mkdir(exist_ok=True)
        shutil.copyfile(path, outdir/path.name)
        windows = []
        start, stop = utc(scenario["A_utc"]), utc(scenario["B_utc"])
        index = 0
        while start < stop:
            end = start+timedelta(hours=scenario["D_hours"])
            i, j = bisect_right(ends, start), bisect_left(starts, end)
            if i == j or starts[i] > start or ends[j-1] < end:
                raise ValueError("Missing mission-window coverage")
            weights = [(min(ends[k], end)-max(starts[k], start)).total_seconds()/3600 for k in range(i, j)]
            values = bounds([r["sun_state"] for r in rows[i:j]], [r["earth_state"] for r in rows[i:j]], weights)
            state, checks, _ = assess(values, preferences, **requirements, duration=scenario["D_hours"])
            soft, _ = assess_soft(values, preferences)
            windows.append(dict(site_id=prefix+"_P1", scenario_status="PROVISIONAL", start_index=index,
                start_utc=start.isoformat().replace("+00:00", "Z"), end_utc=end.isoformat().replace("+00:00", "Z"),
                sunlight_requirement=checks["min_sunlit_fraction"], earth_los_requirement=checks["min_earth_los_fraction"],
                soft_darkness_preference=soft.get("max_darkness_hours", ""),
                soft_earth_blackout_preference=soft.get("max_earth_blackout_hours", ""), decision=state,
                **{f"{key}_{bound}": pair[k] for key, pair in values.items() for k, bound in enumerate(("L", "U"))}))
            start += timedelta(minutes=scenario["start_step_minutes"])
            index += 1
        with (outdir/f"{prefix}_windows.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(windows[0]))
            writer.writeheader()
            writer.writerows(windows)
        print(f"{prefix}: {len(windows)} windows", flush=True)
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.name != "derivation.json":
            outputs[path.relative_to(root).as_posix()] = checksum(path)
    receipt = dict(dataset_version="v0.3.0", source_dataset_version="v0.2.0",
        policy=scenario["decision_policy"], requirements=requirements, soft_preferences=preferences.model_dump(),
        inputs=inputs, outputs=outputs,
        limitations=["Terrain and ephemeris geometry are inherited unchanged; this release changes metric aggregation and decision policy.",
                     "Demo fractions are editable examples, not NASA mission requirements."])
    (target/"derivation.json").write_text(json.dumps(receipt, indent=2)+"\n")
    return receipt


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    build()
