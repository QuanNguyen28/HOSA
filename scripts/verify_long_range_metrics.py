#!/usr/bin/env python3
"""Real HTTP coverage and native-sample checks for prepared 2000–2100 metrics."""
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
from app.services.lunarsight.visibility import visibility
from precompute_catalog import targets

START, END = "2000-01-01T00:00:00Z", "2101-01-01T00:00:00Z"


def payload(target, start, end):
    return MissionRequest(latitude_deg=target["latitude_deg"], longitude_e_deg=target["longitude_e_deg"],
        start_utc=start, end_utc=end, panel_height_m=20., antenna_height_m=20.)


def call(client, request):
    started = perf_counter()
    response = client.post("/api/lunar/point/metrics", json=request.model_dump())
    seconds = perf_counter()-started
    response.raise_for_status()
    result = response.json()
    assert result["decision"] is None and result["evaluation_stages"]["validation"] == "not_started"
    assert result["execution"]["metrics_index_hit"] and 0 < len(result["timeline"]) <= 800
    assert not result["timeline_transport"]["exact_intervals_ready"]
    assert pd.Timestamp(result["timeline"][0]["start_utc"]) == pd.Timestamp(request.start_utc)
    assert pd.Timestamp(result["timeline"][-1]["end_utc"]) == pd.Timestamp(request.end_utc)
    weights = np.array([(pd.Timestamp(row["end_utc"])-pd.Timestamp(row["start_utc"])).total_seconds()/3600 for row in result["timeline"]])
    errors = {}
    for body, expected in [("sun", result["metrics_hours"]["total_sun_hours"]),
                           ("earth", result["metrics_hours"]["total_earth_los_hours"]), ("joint", result["joint_hours"])]:
        integrated = [np.dot(weights, [row[body+"_visible_fraction_"+bound] for row in result["timeline"]]) for bound in ("lower", "upper")]
        errors[body] = float(np.max(np.abs(np.asarray(integrated)-expected)))
    assert max(errors.values()) < 1e-4
    return result, {"http_seconds": seconds, "response_bytes": len(response.content),
        "display_intervals": len(result["timeline"]), "source_intervals": result["timeline_transport"]["source_intervals"],
        "chart_integral_abs_delta_hours": errors}


def verify(base_url):
    root = ROOT/"data/cache/point-analysis"
    before = set((root/"jobs").glob("*.json"))
    pipeline, rows = PointAnalysisPipeline(root), []
    expected_count = int((pd.Timestamp(END)-pd.Timestamp(START)).total_seconds()/300)
    with httpx.Client(base_url=base_url, timeout=120) as client:
        for target in targets():
            request = payload(target, START, END)
            result, timing = call(client, request)
            assert timing["source_intervals"] == expected_count
            assert result["provenance"]["metrics_source"]["kind"] == "prepared_metrics_only"
            row = {"site_ids": target["site_ids"], "full_band": timing, "native_windows": []}
            with pipeline.terrain(request.resolved()) as terrain:
                fine, _, _, _ = pipeline.geometry(terrain, {20.}, lambda _: None)
                base = {h: p.iloc[::2].reset_index(drop=True).assign(az_step_deg=.25) for h, p in fine.items()}
                for a, b in [(START, "2000-01-04T00:00:00Z"), ("2000-12-31T00:00:00Z", "2001-01-03T00:00:00Z"),
                             ("2100-12-29T00:00:00Z", END)]:
                    window = payload(target, a, b)
                    result, timing = call(client, window)
                    sun, earth, _ = pipeline.ephemerides(window, terrain.site, 5)
                    frame = visibility(sun, earth, base[20.], base[20.], solar_disc=True)
                    native = metrics(frame)
                    errors = {key: float(np.max(np.abs(np.asarray(value)-native[key]))) for key, value in result["metrics_hours"].items()}
                    assert max(errors.values()) < 1e-7
                    row["native_windows"].append({"start_utc": a, "end_utc": b, **timing, "native_metric_abs_delta_hours": errors})
            rows.append(row)
            print(json.dumps({"site_ids": row["site_ids"], "full_band_http_seconds": row["full_band"]["http_seconds"], "native_windows_verified": len(row["native_windows"])}), flush=True)
        boundary_cases = []
        for a, b, hours in [("2000-02-28T00:00:00Z", "2000-03-01T00:00:00Z", 48),
                            ("2100-02-28T00:00:00Z", "2100-03-01T00:00:00Z", 24),
                            ("2000-01-01T00:00:00Z", "2050-01-01T00:00:00Z", None),
                            ("2050-01-01T00:00:00Z", "2100-01-01T00:00:00Z", None)]:
            result, timing = call(client, payload(targets()[0], a, b))
            if hours is not None:
                assert result["request"]["duration_hours"] == hours
            boundary_cases.append({"start_utc": a, "end_utc": b, **timing})
        for a, b in [("1999-12-31T00:00:00Z", "2000-01-02T00:00:00Z"), ("2100-12-31T00:00:00Z", "2101-01-02T00:00:00Z")]:
            response = client.post("/api/lunar/point/metrics", json=payload(targets()[0], a, b).model_dump())
            assert response.status_code == 409 and response.json()["detail"]["code"] == "METRICS_NOT_PREPARED"
    assert before == set((root/"jobs").glob("*.json"))
    return {"passed": True, "start_utc": START, "end_utc": END, "sites": rows, "boundary_cases": boundary_cases,
        "no_jobs_created": True, "live_llm_calls": 0,
        "scope": "Real catalog HTTP metrics and charts, full prepared band and native checks at boundaries/cross-year windows. Initial metrics only; no century-long validation or mission PASS is claimed. Timings are local."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.base_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
