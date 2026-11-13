#!/usr/bin/env python3
"""Verify portable real-data artifacts and fresh-result timings, without LLM calls."""
import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.precompute.store import Store, coordinate_key
from app.precompute.geometry import prepared_terrain, decode_profile
from app.precompute.display import decode
from app.mission.models import MissionRequest
from app.point_analysis.pipeline import PointAnalysisPipeline
from app.services.lunarsight.point import _terrain_window_uncached
from precompute_catalog import targets, MESHES


def verify(base_url=None):
    store = Store()
    manifest = store.manifest()
    assert len(manifest["sites"]) == len(targets(include_legacy=True)) == 23
    active_keys = {coordinate_key(t["latitude_deg"], t["longitude_e_deg"]) for t in targets()}
    assert len(active_keys) == 19
    assert len(manifest["meshes"]) == 23*len(MESHES)+2
    profiles, meshes, byte_count = 0, 0, 0
    for key, record in manifest["sites"].items():
        assert set(record["heights_m"]) >= {1., 2., 10., 20.}
        if key in active_keys:
            assert 30. in record["heights_m"]
        for name, reference in record["profiles"].items():
            content = store.read(reference)
            frame = decode_profile(content)
            step = .03125 if name.startswith("fine_") else .0625
            assert np.array_equal(frame.az_deg, np.arange(0, 360, step))
            assert frame.coverage_complete.all() == record["coverage_complete"]
            byte_count += len(content)
            profiles += 1
    for reference in manifest["meshes"].values():
        content = store.read(reference)
        value = decode(content)
        assert value["coverage_status"] == "COVERED"
        grid = value["grid"]
        assert len(grid["elevation_m_row_major"]) == grid["rows"]*grid["columns"]
        byte_count += len(content)
        meshes += 1
    report = {"passed": False, "package": store.descriptor(), "verified_profiles": profiles,
        "verified_meshes": meshes, "referenced_bytes": byte_count, "native_geometry_comparisons": [],
        "fresh_result_timings": [], "live_llm_calls": 0,
        "timing_scope": "Local machine. Fresh result AND geometry caches; packaged terrain and installed shared SPICE kernels/tables. No raw DEM scans."}
    for site_id in ("Site01_P1", "Site04_P1"):
        request = MissionRequest(site_id=site_id, start_utc="2026-11-17T00:00:00Z", offline=True).resolved()
        terrain = prepared_terrain(request, store)
        assert terrain is not None
        native = None
        for path in (ROOT/"data/cache/point-analysis/geometry").glob("*/receipt.json"):
            receipt = json.loads(path.read_text())
            identity = receipt["identity"]
            if (identity["site"] == terrain.site and identity["heights"] == [1., 2.]
                    and identity["az_steps_deg"] == [.125, .25]):
                native = path.parent
                break
        assert native is not None, "Independent native scan fixture is required for release validation"
        fine, short, _ = terrain.profiles([1., 2.], .125)
        for label, group in (("fine", fine), ("short", short)):
            for height, frame in group.items():
                original = pd.read_csv(native/f"{label}_h{height:g}.csv")
                error = float(np.max(np.abs(frame.horizon_deg-original.horizon_deg)))
                assert error < 1e-12
                assert frame.coverage_complete.equals(original.coverage_complete)
                report["native_geometry_comparisons"].append({"site": site_id, "profile": f"{label}_h{height:g}",
                    "max_horizon_difference_deg": error, "identical_coverage": True,
                    "native_receipt": str((native/"receipt.json").relative_to(ROOT))})
    # Exercise all sensitivity/refinement levels using the published profile. A
    # forbidden scanner proves a fresh process/cache does not quietly recompute.
    import app.point_analysis.pipeline as pipeline_module
    original_scan = pipeline_module.scan_horizons
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected raw DEM scan")
    pipeline_module.scan_horizons = forbidden
    try:
        with TemporaryDirectory(prefix="catalog-acceptance-") as temporary:
            for site_id in ("Site01_P1", "Site04_P1", "haworth"):
                pipeline = PointAnalysisPipeline(Path(temporary)/site_id)
                request = MissionRequest(site_id=site_id, start_utc="2026-11-17T00:00:00Z",
                    duration_hours=72, panel_height_m=20., antenna_height_m=20.,
                    min_sunlit_fraction=.8,
                    resolve_indeterminate=True, offline=True)
                stages = []
                started = perf_counter()
                result = pipeline.run(request, stages.append)
                elapsed = perf_counter()-started
                assert not result["execution"]["result_cache_hit"]
                assert "precomputed_horizon" in stages and "terrain_horizon" not in stages
                assert result["decision"] in {"PASS", "FAIL", "INDETERMINATE"}
                report["fresh_result_timings"].append({"site": site_id, "duration_hours": 72,
                    "seconds": elapsed, "decision": result["decision"], "illumination": result["illumination"],
                    "stages": stages, "validation_passed": result["validation"]["passed"]})
    finally:
        pipeline_module.scan_horizons = original_scan
    # The transported numbers must remain identical to direct native DEM display resampling.
    target = next(item for item in targets(include_legacy=True) if "Site04_P1" in item["site_ids"])
    started = perf_counter()
    original = _terrain_window_uncached(target["latitude_deg"], target["longitude_e_deg"], 300., 257, "regional")
    report["direct_mesh_seconds"] = perf_counter()-started
    if base_url:
        with httpx.Client(base_url=base_url, timeout=180) as client:
            url = "/api/lunar/point/terrain-window"
            params = {"latitude": target["latitude_deg"], "longitude": target["longitude_e_deg"],
                      "radius_km": 300, "samples": 257, "detail": "regional"}
            started = perf_counter()
            response = client.get(url, params=params)
            response.raise_for_status()
            elapsed = perf_counter()-started
            assert response.json() == original
            assert response.headers["x-terrain-cache"] == "HIT"
            conditional = client.get(url, params=params, headers={"If-None-Match": response.headers["etag"]})
            assert conditional.status_code == 304
            report["mesh_http"] = {"seconds": elapsed, "cache": "HIT", "identical_to_raw_dem_display": True,
                "gzip_bytes": int(response.headers["content-length"]), "conditional_status": 304}
    report["passed"] = True
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url")
    args = parser.parse_args()
    report = verify(args.base_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({key: report[key] for key in ("passed", "package", "verified_profiles", "verified_meshes")}, indent=2))
