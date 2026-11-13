#!/usr/bin/env python3
"""Extend verified catalog horizons for viewer presets without rebuilding meshes."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.mission.models import MissionRequest
from app.point_analysis.sources import TerrainInputs
from app.point_analysis.geometry import scan_horizons, verify_profiles, METHOD_VERSION
from app.precompute.geometry import FINE_STEP, SHORT_STEP, encode_profile, compatible_sources
from app.precompute.store import Store, coordinate_key
from precompute_catalog import targets


def extend(target, root):
    started = perf_counter()
    store = Store(root)
    key = coordinate_key(target["latitude_deg"], target["longitude_e_deg"])
    record = store.manifest()["sites"].get(key)
    if not record or record["geometry_method"] != METHOD_VERSION or not compatible_sources(record):
        raise ValueError("A compatible prepared observer is required; rebuild catalog after source changes")
    wanted = {2., 10., 20., 30.}
    missing = wanted-set(record["heights_m"])
    for reference in record["profiles"].values():
        store.read(reference)
    if not missing:
        return {"site_ids": target["site_ids"], "status": "already_prepared", "heights_m": record["heights_m"],
                "elapsed_seconds": perf_counter()-started}
    request = MissionRequest(latitude_deg=target["latitude_deg"], longitude_e_deg=target["longitude_e_deg"],
        start_utc="2026-11-24T00:00:00Z", panel_height_m=30., antenna_height_m=30.)
    with TerrainInputs(request) as terrain:
        for name in ("lon_e_deg", "lat_deg", "dem_z_m"):
            if abs(terrain.site[name]-record["site"][name]) > 1e-9:
                raise ValueError("Observer source changed; do not mix old and new horizons")
        profiles = dict(record["profiles"])
        references = {label: dict(values) for label, values in record["references"].items()}
        complete = record["coverage_complete"]
        for label, radius, step in (("fine", 400000, FINE_STEP), ("short", 300000, SHORT_STEP)):
            print(json.dumps({"site_ids": target["site_ids"], "stage": label, "new_heights_m": sorted(missing)}), flush=True)
            group = scan_horizons(terrain, missing, radius=radius, az_step=step)
            references[label].update(verify_profiles(group, terrain.site))
            for height, profile in group.items():
                profiles[f"{label}_h{height:g}"] = store.put(encode_profile(profile), "npz")
                complete = complete and bool(profile.coverage_complete.all())
        record.update(profiles=profiles, references=references, coverage_complete=complete,
                      heights_m=sorted(set(record["heights_m"])|wanted))
        store.publish(key, record)
    return {"site_ids": target["site_ids"], "status": "extended", "heights_m": record["heights_m"],
            "elapsed_seconds": perf_counter()-started, "enu_reference_verified": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    records, selected = [], targets()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = [pool.submit(extend, target, args.root) for target in selected]
        for future in as_completed(pending):
            record = future.result()
            records.append(record)
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps({"passed": len(records)==len(selected), "records": records,
                "sites_total": len(selected), "live_llm_calls": 0}, indent=2)+"\n")
            print(json.dumps(record), flush=True)
