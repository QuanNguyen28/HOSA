#!/usr/bin/env python3
"""Audit every active NASA observer/height and display mesh from actual blobs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.mission.targets import default_sites
from app.precompute.geometry import HEIGHTS, decode_profile, compatible_sources
from app.precompute.display import decode
from app.precompute.store import Store, coordinate_key, mesh_key
from app.point_analysis.geometry import verify_profiles
from precompute_catalog import targets, MESHES


def verify():
    catalog = default_sites()
    assert len(catalog) == 27
    metadata = json.loads((ROOT / "manifests/nasa-south-pole-sites.receipt.json").read_text())
    assert metadata["csv_sha256"] == hashlib.sha256((ROOT / "manifests/nasa-south-pole-sites.csv").read_bytes()).hexdigest()
    selected, store = targets(), Store()
    assert len(selected) == 26
    manifest, rows = store.manifest(), []
    for target in selected:
        record = manifest["sites"][coordinate_key(target["latitude_deg"], target["longitude_e_deg"])]
        assert compatible_sources(record)
        assert record["site"]["lat_deg"] == target["latitude_deg"]
        assert record["site"]["lon_e_deg"] == target["longitude_e_deg"]
        assert record["observer_source"]["resolution_m"] == 5
        assert set(record["heights_m"]) == set(HEIGHTS)
        assert np.isfinite(record["site"]["dem_z_m"])
        references, profile_count, byte_count = {}, 0, 0
        for label, step in (("fine", .03125), ("short", .0625)):
            profiles = {}
            for height in HEIGHTS:
                reference = record["profiles"][f"{label}_h{height:g}"]
                content = store.read(reference)
                frame = decode_profile(content)
                assert len(frame) == round(360 / step)
                assert np.array_equal(frame.az_deg, np.arange(0, 360, step))
                assert (frame.height_m == height).all()
                assert not frame.horizon_deg.isna().any()
                profiles[height] = frame
                profile_count += 1
                byte_count += len(content)
            reference = verify_profiles(profiles, record["site"])
            assert all(result["passed"] for result in reference.values())
            references[label] = reference
            for lower, higher in zip(HEIGHTS, HEIGHTS[1:]):
                assert np.all(profiles[higher].horizon_deg <= profiles[lower].horizon_deg + 1e-12)
        for config in MESHES:
            reference = manifest["meshes"][mesh_key(target["latitude_deg"], target["longitude_e_deg"], *config)]
            content = store.read(reference)
            mesh = decode(content)
            assert mesh["coverage_status"] == "COVERED"
            assert len(mesh["grid"]["elevation_m_row_major"]) == mesh["grid"]["rows"] * mesh["grid"]["columns"]
            byte_count += len(content)
        row = {"site_ids": target["site_ids"], "names": [catalog[s]["name"] for s in target["site_ids"]],
            "coordinate": record["site"], "observer_source": record["observer_source"],
            "heights_m": record["heights_m"], "verified_profiles": profile_count, "verified_meshes": len(MESHES),
            "reference_checks": references, "height_monotonicity_passed": True,
            "coverage_complete": record["coverage_complete"], "referenced_bytes": byte_count}
        rows.append(row)
        print(json.dumps({"verified": row["names"], "profiles": profile_count}), flush=True)
    return {"passed": True, "default_entries": len(catalog), "coordinates": len(selected),
        "viewer_heights_m": [2, 10, 20, 30], "metric_configurations_expected": 104,
        "verified_profiles": sum(r["verified_profiles"] for r in rows),
        "verified_meshes": sum(r["verified_meshes"] for r in rows), "sites": rows,
        "live_llm_calls": 0,
        "scope": "Published NASA centres, current verified source inventory, profile/blob integrity, independent Cartesian ENU blocker references, height monotonicity and display meshes. No mission PASS or continuous-time visibility certification."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("passed", "default_entries", "coordinates", "verified_profiles", "verified_meshes")}), flush=True)
