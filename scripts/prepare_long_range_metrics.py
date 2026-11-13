#!/usr/bin/env python3
"""Build compact catalog metrics/charts in resumable yearly native chunks."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter, sleep

import pandas as pd
from filelock import FileLock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"backend"))
from app.mission.identity import digest
from app.mission.models import MissionRequest
from app.point_analysis import metric_index
from app.point_analysis.pipeline import PointAnalysisPipeline, atomic_json
from app.point_analysis.prepared_metrics import PreparedMetrics, atomic_bytes
from app.services.lunarsight.acquire import hashfile
from app.services.lunarsight.visibility import visibility
from precompute_catalog import targets


def prepare(target, start, end, panel, antenna, root, wait_prepared_seconds=0):
    started = perf_counter()
    request = MissionRequest(latitude_deg=target["latitude_deg"], longitude_e_deg=target["longitude_e_deg"],
        start_utc=start, end_utc=end, panel_height_m=panel, antenna_height_m=antenna).resolved()
    pipeline, store = PointAnalysisPipeline(root), PreparedMetrics(root)
    if wait_prepared_seconds:
        from app.precompute.geometry import prepared_terrain
        deadline = perf_counter() + wait_prepared_seconds
        while prepared_terrain(request) is None:
            if perf_counter() >= deadline:
                raise TimeoutError(f"Prepared terrain not available: {target['site_ids']}")
            sleep(1)
    boundaries = sorted({pd.Timestamp(start), pd.Timestamp(end), *pd.date_range(start, end, freq="YS")})
    completed, chunks = [], []
    with pipeline.terrain(request) as terrain:
        fine, _, _, geometry_receipt = pipeline.geometry(terrain, {panel, antenna}, lambda _: None)
        base = {h: p.iloc[::2].reset_index(drop=True).assign(az_step_deg=.25) for h, p in fine.items()}
        source = pipeline.initial_source(request, terrain, base)
        key = digest(source)
        pipeline.shared_ephemeris.exact(boundaries)
        for begin, stop in zip(boundaries[:-1], boundaries[1:]):
            coverage = {"start_utc": begin.isoformat(), "end_utc": stop.isoformat()}
            directory = store.root/key/".parts"/digest(coverage)
            directory.mkdir(parents=True, exist_ok=True)
            with FileLock(str(directory/"part.lock")):
                receipt = directory/"receipt.json"
                if receipt.is_file():
                    record = json.loads(receipt.read_text())
                    if (record["identity_sha256"] != key or record["metrics_index"]["version"] != metric_index.VERSION
                            or record["metrics_index"]["sha256"] != hashfile(directory/"metrics.npz")):
                        raise ValueError("Metric part is corrupt or incompatible; inspect before rebuilding")
                else:
                    part = MissionRequest(latitude_deg=request.latitude_deg, longitude_e_deg=request.longitude_e_deg,
                        start_utc=begin.isoformat(), end_utc=stop.isoformat(), panel_height_m=panel, antenna_height_m=antenna)
                    sun, earth, ephemerides = pipeline.ephemerides(part, terrain.site, 5)
                    if (pipeline.series_identity(sun, earth, base, part) != source or any(
                            r["missing_timestamps"] or r["missing_angles"] or not r["interpolation_validation"]["passed"] for r in ephemerides)):
                        raise ValueError(f"Ephemeris validation failed: {target['site_ids']} {begin}: {ephemerides}")
                    frame = visibility(sun, earth, base[panel], base[antenna], solar_disc=True)
                    native_hash = hashlib.sha256(pd.util.hash_pandas_object(frame, index=True).values.tobytes()).hexdigest()
                    content, full_metrics = metric_index.build(frame)
                    atomic_bytes(directory/"metrics.npz", content)
                    record = {"identity_sha256": key, **coverage, "native_intervals": len(frame), "native_frame_sha256": native_hash,
                        "ephemerides": ephemerides, "geometry_identity": geometry_receipt["identity"],
                        "metrics_index": {"version": metric_index.VERSION, "sha256": hashfile(directory/"metrics.npz"), "full_metrics": full_metrics}}
                    atomic_json(receipt, record)
                    del sun, earth, frame, content
                completed.append(directory/"metrics.npz")
                chunks.append({**coverage, "receipt_sha256": hashfile(receipt), "index_sha256": record["metrics_index"]["sha256"],
                    "native_frame_sha256": record["native_frame_sha256"], "native_intervals": record["native_intervals"]})
            print(json.dumps({"site_ids": target["site_ids"], "through_utc": stop.isoformat(), "parts_done": len(completed),
                "parts_total": len(boundaries)-1, "elapsed_seconds": perf_counter()-started}), flush=True)
    content, full_metrics = metric_index.combine_parts(path.read_bytes() for path in completed)
    directory = store.publish(source, start, end, content, full_metrics, chunks)
    measured = perf_counter()
    result = store.query(source, start, end)
    assert result is not None and result["metrics_hours"] == full_metrics
    return {"site_ids": target["site_ids"], "start_utc": start, "end_utc": end, "panel_m": panel, "antenna_m": antenna,
        "native_intervals": sum(c["native_intervals"] for c in chunks), "parts": len(chunks),
        "index_bytes": (directory/"metrics.npz").stat().st_size, "source_identity_sha256": key,
        "index_sha256": hashfile(directory/"metrics.npz"), "build_seconds": measured-started,
        "first_query_seconds": perf_counter()-measured, "display_intervals": len(result["timeline"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2000-01-01T00:00:00Z")
    parser.add_argument("--end", default="2101-01-01T00:00:00Z")
    parser.add_argument("--sites", nargs="+")
    parser.add_argument("--viewer-heights", nargs="+", type=float, choices=(2., 10., 20., 30.),
                        help="Prepare equal panel/antenna heights for each selected viewer preset")
    parser.add_argument("--panel", type=float, default=20.)
    parser.add_argument("--antenna", type=float, default=20.)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--wait-prepared-seconds", type=int, default=0,
                        help="Wait for a concurrent terrain build instead of doing a duplicate raw DEM scan")
    parser.add_argument("--root", type=Path, default=ROOT/"data/cache/point-analysis")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    selected = [t for t in targets(include_legacy=bool(args.sites)) if not args.sites or set(args.sites)&set(t["site_ids"])]
    if not selected or (args.sites and set(args.sites)-{s for t in selected for s in t["site_ids"]}):
        parser.error("Unknown site ID")
    records = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        hardware = [(h, h) for h in args.viewer_heights] if args.viewer_heights else [(args.panel, args.antenna)]
        total = len(selected)*len(hardware)
        pending = [pool.submit(prepare, target, args.start, args.end, panel, antenna, args.root, args.wait_prepared_seconds)
                   for target in selected for panel, antenna in hardware]
        for future in as_completed(pending):
            row = future.result()
            records.append(row)
            print(json.dumps({"site_complete": row}), flush=True)
            atomic_json(args.report, {"passed": len(records)==total, "records": records, "sites_total": len(selected),
                "configurations_total": total, "hardware_pairs_m": hardware,
                "start_utc": args.start, "end_utc": args.end, "live_llm_calls": 0,
                "scope": "Compact nominal five-minute metrics/charts only; yearly source hashes and interpolation checks retained. Full native timelines and mission validation are computed on demand."})
