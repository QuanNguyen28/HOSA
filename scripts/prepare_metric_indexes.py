#!/usr/bin/env python3
"""Index existing nominal catalog series for fast metrics, without recomputation."""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.mission.identity import digest
from app.mission.models import MissionRequest
from app.point_analysis.pipeline import PointAnalysisPipeline
from app.point_analysis import metric_index
from precompute_catalog import targets


def prepare(root, sites=None, panel=20., antenna=20.):
    pipeline, output = PointAnalysisPipeline(root), []
    for target in targets():
        if sites and not set(target["site_ids"])&set(sites):
            continue
        request = MissionRequest(latitude_deg=target["latitude_deg"], longitude_e_deg=target["longitude_e_deg"],
            start_utc="2026-01-01T00:00:00Z", duration_hours=24., panel_height_m=panel, antenna_height_m=antenna).resolved()
        with pipeline.terrain(request) as terrain:
            fine, _, _, _ = pipeline.geometry(terrain, {panel, antenna}, lambda _: None)
            base = {h: p.iloc[::2].reset_index(drop=True).assign(az_step_deg=.25) for h, p in fine.items()}
            source = pipeline.initial_source(request, terrain, base)
        for receipt in sorted((pipeline.physics.root/digest(source)).glob("*/receipt.json")):
            started = perf_counter()
            pipeline.physics.prepare_index(receipt)
            build_seconds = perf_counter()-started
            record = json.loads(receipt.read_text())
            started = perf_counter()
            summary = metric_index.query(receipt.parent, record["metrics_index"], record["start_utc"], record["end_utc"])
            seconds = perf_counter()-started
            assert summary and summary["metrics_hours"] == record["metrics_index"]["full_metrics"]
            row = {"site_ids": target["site_ids"], "start_utc": record["start_utc"], "end_utc": record["end_utc"],
                "source_intervals": summary["source_intervals"], "index_bytes": (receipt.parent/"metrics.npz").stat().st_size,
                "build_seconds": build_seconds, "metrics_query_seconds": seconds}
            output.append(row)
            print(json.dumps(row), flush=True)
    return {"passed": True, "records": output, "live_llm_calls": 0,
        "scope": "Indexed existing verified nominal physical series only. Indexed metrics are provisional; no request validation or decisions are preapproved. Timings measure index lookup, not end-to-end HTTP latency."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT/"data/cache/point-analysis")
    parser.add_argument("--sites", nargs="+")
    parser.add_argument("--panel", type=float, default=20.)
    parser.add_argument("--antenna", type=float, default=20.)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.root, args.sites, args.panel, args.antenna)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+"\n")
