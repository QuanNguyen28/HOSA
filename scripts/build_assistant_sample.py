"""Rebuild the small, derived science sample from committed versioned CSVs."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests/fixtures/assistant/window_sample.json"


def build() -> dict:
    rows, sources = [], {}
    for site in ("Site01", "Site04"):
        path = ROOT / f"data/processed/lunarsight/v0.2.0/visibility/{site}_windows.csv"
        source = str(path.relative_to(ROOT))
        sources[source] = hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if int(row["start_index"]) in (0, 288, 576):
                    # Do not reuse cached decision labels: live constraints may differ.
                    rows.append({"site_id": row["site_id"], "start_index": int(row["start_index"]),
                        "start_utc": row["start_utc"], "end_utc": row["end_utc"],
                        "metrics": {metric: [float(row[metric+"_L"]), float(row[metric+"_U"])] for metric in
                            ("total_sun_hours", "longest_dark_hours", "longest_blackout_hours", "longest_joint_hours")},
                        "source": source})
    return {"data_kind": "derived_versioned_data", "dataset_version": "v0.2.0", "status": "PROVISIONAL",
        "note": "Six 72-hour windows, not six independent missions or a model training set.",
        "source_hashes": sources, "windows": rows}


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
