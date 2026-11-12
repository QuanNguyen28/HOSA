#!/usr/bin/env python3
"""Real prepared-metrics HTTP checks, independent of analysis/validation jobs."""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.mission.models import MissionRequest
from app.mission.evaluation import metrics
from app.point_analysis.pipeline import PointAnalysisPipeline
from precompute_catalog import targets


def verify(base_url):
    root = ROOT/"data/cache/point-analysis"
    before = set((root/"jobs").glob("*.json"))
    report = {"passed": False, "cases": [], "catalog": [], "live_llm_calls": 0,
        "scope": "Real HTTP prepared metrics and bounded preview charts; local timings, no new analysis jobs. Initial/provisional metrics are compared with native nominal samples after timing. Unprepared coverage must not clamp or invent values."}
    pipeline = PointAnalysisPipeline(root)
    with httpx.Client(base_url=base_url, timeout=60) as client:
        for year in (2036, 2046, 2056):
            request = MissionRequest(site_id="Site04_P1", start_utc="2026-11-24T00:00:00Z", end_utc=f"{year}-11-24T00:00:00Z", panel_height_m=20., antenna_height_m=20.)
            samples = []
            for _ in range(3):
                started = perf_counter()
                response = client.post("/api/lunar/point/metrics", json=request.model_dump())
                samples.append(perf_counter()-started)
                response.raise_for_status()
                result = response.json()
                assert result["decision"] is None and 0 < len(result["timeline"]) <= 800
                assert result["timeline_transport"]["exact_intervals_ready"] is False
                assert result["execution"]["metrics_index_hit"] and result["evaluation_stages"]["validation"] == "not_started"
            # Independent native scan is verification only, never part of HTTP timing.
            resolved = request.resolved()
            with pipeline.terrain(resolved) as terrain:
                fine, _, _, _ = pipeline.geometry(terrain, {20.}, lambda _: None)
                base = {h: p.iloc[::2].reset_index(drop=True).assign(az_step_deg=.25) for h, p in fine.items()}
                source = pipeline.initial_source(resolved, terrain, base)
            frame = pipeline.physics.load(source, request.start_utc, request.end_utc)
            native = metrics(frame)
            errors = {key: float(np.max(np.abs(np.asarray(pair)-native[key]))) for key, pair in result["metrics_hours"].items()}
            assert max(errors.values()) < 1e-4  # <0.36 seconds of accumulated floating-point duration.
            chart_errors = {}
            weights = np.array([(pd.Timestamp(row["end_utc"])-pd.Timestamp(row["start_utc"])).total_seconds()/3600 for row in result["timeline"]])
            for body, expected in [("sun", native["total_sun_hours"]), ("earth", native["total_earth_los_hours"]), ("joint", result["joint_hours"])]:
                integrated = [np.dot(weights, [row[body+"_visible_fraction_"+bound] for row in result["timeline"]]) for bound in ("lower", "upper")]
                chart_errors[body] = float(np.max(np.abs(np.asarray(integrated)-expected)))
            assert max(chart_errors.values()) < 1e-4
            report["cases"].append({"years": year-2026, "http_seconds": samples, "response_bytes": len(response.content),
                "source_intervals": result["timeline_transport"]["source_intervals"], "metrics_hours": result["metrics_hours"],
                "joint_hours": result["joint_hours"], "native_metric_abs_delta_hours": errors,
                "chart_display_intervals": len(result["timeline"]), "chart_integral_abs_delta_hours": chart_errors})
            del frame
        for target in targets():
            request = MissionRequest(latitude_deg=target["latitude_deg"], longitude_e_deg=target["longitude_e_deg"],
                start_utc="2026-11-24T00:00:00Z", duration_hours=72., panel_height_m=20., antenna_height_m=20.)
            started = perf_counter()
            response = client.post("/api/lunar/point/metrics", json=request.model_dump())
            seconds = perf_counter()-started
            response.raise_for_status()
            assert response.json()["decision"] is None
            report["catalog"].append({"site_ids": target["site_ids"], "http_seconds": seconds})
        missing = MissionRequest(site_id="Site04_P1", start_utc="2026-11-24T00:00:00Z", end_utc="2076-11-24T00:00:00Z", panel_height_m=20., antenna_height_m=20.)
        response = client.post("/api/lunar/point/metrics", json=missing.model_dump())
        if response.status_code == 200:
            fifty = response.json()
            assert fifty["decision"] is None and fifty["timeline"] and fifty["execution"]["metrics_index_hit"]
            fifty_status = "prepared"
        else:
            assert response.status_code == 409 and response.json()["detail"]["code"] == "METRICS_NOT_PREPARED"
            fifty_status = "METRICS_NOT_PREPARED"
    assert before == set((root/"jobs").glob("*.json"))
    report.update(passed=True, no_jobs_created=True, fifty_year_window_status=fifty_status)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.base_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"passed": report["passed"], "cases": [{"years": c["years"], "http_seconds": c["http_seconds"]} for c in report["cases"]],
        "catalog_points": len(report["catalog"])}, indent=2))
