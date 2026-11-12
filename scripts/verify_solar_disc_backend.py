#!/usr/bin/env python3
"""Real-data solar-disc acceptance and timings; no model calls or synthetic DEM.

JPL comparisons use hash-checked, native 1/5-minute observer responses. Timing
uses isolated result caches seeded with existing terrain, not a cold DEM scan.
"""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import sys
import csv
import io
import httpx

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.mission.models import MissionRequest
from app.point_analysis.pipeline import PointAnalysisPipeline
from app.point_analysis.sources import TerrainInputs
from app.services.lunarsight.solar_disc import fractions
from app.services.lunarsight.shared_ephemeris import SharedEphemeris
from verify_compute_and_resolution import seed, measured


def verify_api(base_url):
    cases = []
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=180) as client:
        for name in ("pass", "fail"):
            request = json.loads((ROOT/f"docs/examples/point-analysis-outside-{name}-request.json").read_text())
            request.update(illumination_model="solar_disc", offline=True, resolve_indeterminate=True)
            started = perf_counter()
            response = client.post("/api/lunar/point/analyze", json=request)
            response.raise_for_status()
            point = response.json()
            point_seconds = perf_counter()-started
            expected = "PASS" if name == "pass" else "FAIL"
            assert point["decision"] == expected
            query = {key: request[key] for key in ("illumination_model", "duration_hours", "min_sunlit_fraction", "constraints", "contact_requirements", "offline", "resolve_indeterminate")}
            query.update(targets=[{key: request[key] for key in ("latitude_deg", "longitude_e_deg")}],
                arrival_utc=request["start_utc"], hardware={"sun_panel": request["panel_height_m"], "earth_antenna": request["antenna_height_m"]})
            compared = client.post("/api/planning/compare", json=query)
            compared.raise_for_status()
            compared = compared.json()
            until = (pd.Timestamp(request["start_utc"])+pd.Timedelta(minutes=5)).isoformat()
            searched = client.post("/api/planning/windows/search", json={**query, "until_utc": until, "start_step_minutes": 5})
            searched.raise_for_status()
            searched = searched.json()
            for result in (compared, searched):
                candidate = result["candidates"][0]
                assert candidate["decision"] == expected and candidate["metrics"] == point["metrics_hours"]
                assert candidate["analysis_result_id"] == point["result_id"]
                assert candidate["illumination"] == point["illumination"]
            exported = client.get(f'/api/planning/results/{compared["result_id"]}', params={"format": "csv"})
            exported.raise_for_status()
            row = next(csv.DictReader(io.StringIO(exported.text)))
            assert row["illumination_model"] == "solar_disc"
            assert float(row["total_sun_hours_L"]) == point["metrics_hours"]["total_sun_hours"][0]
            cases.append({"case": name, "decision": point["decision"], "result_id": point["result_id"],
                "point_api_seconds": point_seconds, "point_result_cache_hit": point["execution"]["result_cache_hit"],
                "point_compare_search_csv_consistent": True})
        response = client.get("/api/assistant/capabilities")
        response.raise_for_status()
        caps = response.json()
    return {"passed": True, "base_url": base_url, "cases": cases,
        "assistant_provider": caps["provider"], "live_llm_calls": 0}


def verify():
    source = ROOT/"data/cache/point-analysis"
    pipeline = PointAnalysisPipeline(source)
    report = {"passed": False, "ephemeris": pipeline.shared_ephemeris.identity(), "jpl_comparisons": [], "cases": [],
        "timing_scope": "Isolated completed-result caches; installed, cached NASA terrain; local shared SPICE tables. No network in calculations.",
        "live_llm_calls": 0}
    for site in ("Site01_P1", "Site04_P1"):
        request = MissionRequest(site_id=site, illumination_model="sun_center", start_utc="2026-11-17T00:00:00Z", duration_hours=72., offline=True).resolved()
        with TerrainInputs(request) as terrain:
            for step in (5, 1):
                sun, earth, receipts = pipeline.ephemerides(request, terrain.site, step)
                for target, height, native in ((10, 1., sun), (399, 2., earth)):
                    shared, receipt = pipeline.shared_ephemeris.sample(terrain.site, target, height, request.start_utc, request.end_utc, step)
                    az_error = float(np.max(abs((shared.az_deg-native.az_deg+180)%360-180)))
                    el_error = float(np.max(abs(shared.el_deg-native.el_deg)))
                    assert max(az_error, el_error) < .001
                    report["jpl_comparisons"].append({"site": site, "target": target, "step_minutes": step,
                        "samples": len(native), "max_az_error_deg": az_error, "max_el_error_deg": el_error,
                        "shared_interpolation_check": receipt["interpolation_validation"],
                        "jpl_sources": [{k: r[k] for k in ("raw_file", "sha256", "observer_frame")}
                                        for r in receipts if r["target"] == target]})
    examples = ROOT/"docs/examples"
    cases = [("outside-pass", json.loads((examples/"point-analysis-outside-pass-request.json").read_text())),
             ("outside-fail", json.loads((examples/"point-analysis-outside-fail-request.json").read_text())),
             ("Site01-240h", json.loads((examples/"point-analysis-long-end-date-request.json").read_text()))]
    with TemporaryDirectory(prefix="solar-acceptance-", dir=source) as temporary:
        root = Path(temporary)
        seed(root)
        for name, data in cases:
            request = MissionRequest.model_validate({**data, "illumination_model": "solar_disc", "offline": True, "resolve_indeterminate": True})
            result, timing = measured(PointAnalysisPipeline, root, request)
            assert result["decision"] == ("FAIL" if name == "outside-fail" else "PASS")
            assert all(r["provider"].startswith("shared-spice") for r in result["provenance"]["ephemerides"])
            report["cases"].append({"name": name, "request": request.model_dump(), "illumination": result["illumination"],
                **timing, "geometry": result["provenance"]["geometry"]["identity"], "validation": result["validation"]})
    # Real ephemeris on a declared flat skyline isolates occultation from DEM.
    # This is an astronomy regression, not a terrain/site feasibility claim.
    observer = {"lon_e_deg": 0., "lat_deg": -85.45, "dem_z_m": 0.}
    ephemeris = SharedEphemeris()
    sun, _ = ephemeris.sample(observer, 10, 2., "2026-03-03T09:00:00Z", "2026-03-03T14:00:00Z", 1)
    earth, _ = ephemeris.sample(observer, 399, 2., "2026-03-03T09:00:00Z", "2026-03-03T14:00:00Z", 1)
    az = np.arange(0, 360, .25)
    horizon = pd.DataFrame({"az_deg": az, "az_step_deg": .25, "horizon_deg": 0., "coverage_complete": True})
    lo, hi = fractions(sun, earth, horizon)
    reference, _ = fractions(sun, earth, horizon, strips=2048)
    assert (hi == 0).any() and (lo == 1).any() and ((lo > 0) & (lo < 1)).any()
    assert float(np.max(abs(lo-reference))) < .002
    report["eclipse_regression"] = {"observer": observer, "skyline": "declared flat 0 degrees; isolates real SPICE occultation geometry",
        "first_totality_utc": sun.index[np.flatnonzero(hi == 0)[0]].isoformat(),
        "last_totality_sample_utc": sun.index[np.flatnonzero(hi == 0)[-1]].isoformat(),
        "max_fraction_difference_64_vs_2048_strips": float(np.max(abs(lo-reference)))}
    report["passed"] = True
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", help="Also verify running Point/Compare/Search/CSV endpoints; no LLM inference")
    args = parser.parse_args()
    report = verify()
    if args.base_url:
        report["live_api"] = verify_api(args.base_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"passed": report["passed"], "jpl_comparisons": len(report["jpl_comparisons"]),
        "cases": [{k: c[k] for k in ("name", "decision", "elapsed_seconds", "cached_result_seconds")} for c in report["cases"]]}, indent=2))
