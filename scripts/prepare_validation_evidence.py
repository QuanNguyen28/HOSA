#!/usr/bin/env python3
"""Prepare reusable numerical evidence for an exact MissionRequest window."""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))

from app.mission.models import MissionRequest
from app.mission.resolution import FINE_AZIMUTH_STEPS
from app.point_analysis.pipeline import PointAnalysisPipeline


def prepare(request, root, all_refinements=False):
    pipeline = PointAnalysisPipeline(root)
    request = request.resolved()
    # Stored evidence never contains a threshold-specific decision. The
    # preparation request itself also asks for no mission feasibility judgment.
    request = request.model_copy(update={"min_sunlit_fraction": None, "min_earth_los_fraction": None,
        "contact_requirements": None, "evaluation_policy": "complete", "resolve_indeterminate": False})
    ephemerides, records = None, []
    with pipeline.terrain(request) as terrain:
        def inputs():
            nonlocal ephemerides
            if ephemerides is None:
                sun, earth, r5 = pipeline.ephemerides(request, terrain.site, 5)
                sun1, earth1, r1 = pipeline.ephemerides(request, terrain.site, 1)
                ephemerides = sun, earth, sun1, earth1, r5, r1
            return ephemerides
        steps = (.125, *FINE_AZIMUTH_STEPS) if all_refinements else (.125,)
        for step in steps:
            started = perf_counter()
            fine, shorter, seams, _ = pipeline.geometry(terrain,
                {request.panel_height_m, request.antenna_height_m}, lambda _: None, az_step=step)
            _, _, validation, _, _, _ = pipeline.evaluate_geometry(request, terrain, fine, shorter, seams, inputs, step)
            records.append({"fine_az_step_deg": step, "evidence": validation["evidence_cache"],
                "elapsed_seconds": perf_counter()-started})
    return {"prepared": True, "request": request.model_dump(), "records": records,
        "scope": "Request-independent numerical evidence for this exact window; not a mission PASS or full-century preparation.",
        "live_llm_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT/"data/cache/point-analysis")
    parser.add_argument("--all-refinements", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    request = MissionRequest.model_validate(json.loads(args.request.read_text()))
    if request.illumination_model != "solar_disc":
        parser.error("Reusable numerical evidence currently requires solar_disc")
    report = prepare(request, args.root, args.all_refinements)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))
