#!/usr/bin/env python3
"""Independent native one-minute JPL checks near both ends of 2000–2100."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.mission.models import MissionRequest
from app.point_analysis.pipeline import PointAnalysisPipeline


def verify():
    pipeline = PointAnalysisPipeline(ROOT/"data/cache/point-analysis")
    cases = []
    for site in ("Site01_P1", "Site04_P1"):
        for start in ("2000-01-01T00:00:00Z", "2100-12-31T00:00:00Z"):
            request = MissionRequest(site_id=site, illumination_model="sun_center", start_utc=start,
                duration_hours=1., panel_height_m=20., antenna_height_m=20.).resolved()
            with pipeline.terrain(request) as terrain:
                sun, earth, receipts = pipeline.ephemerides(request, terrain.site, 1)
                for target, native in ((10, sun), (399, earth)):
                    shared, receipt = pipeline.shared_ephemeris.sample(terrain.site, target, 20., request.start_utc, request.end_utc, 1)
                    assert shared.index.equals(native.index) and len(native) == 61
                    az = float(np.max(np.abs((shared.az_deg-native.az_deg+180)%360-180)))
                    el = float(np.max(np.abs(shared.el_deg-native.el_deg)))
                    assert np.isfinite([az, el]).all() and max(az, el) < .001
                    row = {"site_id": site, "start_utc": start, "target": target, "height_m": 20., "step_minutes": 1,
                        "samples": len(native), "max_az_error_deg": az, "max_el_error_deg": el,
                        "shared_interpolation_check": receipt["interpolation_validation"],
                        "jpl_sources": [{k: r[k] for k in ("raw_file", "sha256", "observer_frame")} for r in receipts if r["target"] == target]}
                    cases.append(row)
                    print(json.dumps({k: row[k] for k in ("site_id", "start_utc", "target", "max_az_error_deg", "max_el_error_deg")}), flush=True)
    return {"passed": True, "cases": cases, "live_llm_calls": 0,
        "scope": "Independent native one-minute JPL Horizons observer angles versus shared SPICE at selected windows near each boundary. Not continuous-time certification or a validation PASS for the whole century."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
