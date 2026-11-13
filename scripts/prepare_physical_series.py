#!/usr/bin/env python3
"""Prepare nominal 5-minute solar-disc/Earth/Joint series before deployment.

This band is cache coverage, never a limit on requested mission dates/durations.
Validation and requirements remain request-specific. No LLM calls.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.mission.models import MissionRequest
from app.point_analysis.pipeline import PointAnalysisPipeline
from precompute_catalog import targets


def prepare(target, start, end, panel, antenna, root):
    started = perf_counter()
    request = MissionRequest(latitude_deg=target["latitude_deg"], longitude_e_deg=target["longitude_e_deg"],
        start_utc=start, end_utc=end, panel_height_m=panel, antenna_height_m=antenna)
    pipeline = PointAnalysisPipeline(root)
    frame = pipeline.prepare_physics(request)
    warm = perf_counter()
    repeat = pipeline.prepare_physics(request)
    assert repeat.attrs.get("physical_series_cache_hit") and len(repeat) == len(frame)
    return {"site_ids": target["site_ids"], "native_intervals": len(frame), "build_seconds": warm-started,
            "cached_read_seconds": perf_counter()-warm}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-01-01T00:00:00Z")
    parser.add_argument("--end", default="2028-01-01T00:00:00Z")
    parser.add_argument("--sites", nargs="+")
    parser.add_argument("--panel", type=float, default=20.)
    parser.add_argument("--antenna", type=float, default=20.)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--root", type=Path, default=ROOT/"data/cache/point-analysis")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    selected = [t for t in targets(include_legacy=bool(args.sites)) if not args.sites or set(args.sites)&set(t["site_ids"])]
    if not selected or (args.sites and set(args.sites)-{s for t in selected for s in t["site_ids"]}):
        parser.error("Unknown site ID")
    records = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = [pool.submit(prepare, target, args.start, args.end, args.panel, args.antenna, args.root) for target in selected]
        for future in as_completed(pending):
            record = future.result()
            records.append(record)
            print(json.dumps(record), flush=True)
    report = {"passed": True, "start_utc": args.start, "end_utc": args.end, "panel_m": args.panel,
        "antenna_m": args.antenna, "records": records, "live_llm_calls": 0,
        "scope": "Prepared nominal physical samples; no requirements or scientific validation results are preapproved."}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+"\n")
