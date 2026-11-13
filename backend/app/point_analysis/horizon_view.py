"""Read-only horizon and bounded whole-mission sky products for Explore.

These products never run requirements, validation, or an uncached DEM scan.
Sky tracks use checked shared SPICE interpolation, not mission averages.
"""
import json
import math

import numpy as np
import pandas as pd
from filelock import FileLock

from app.core.errors import DomainError
from app.mission.identity import digest
from .geometry import METHOD_VERSION
from .pipeline import atomic_json

VERSION = "horizon-view-1"
TRACK_CHUNK_DAYS = 120


def _profiles(request, pipeline, terrain):
    heights = set((request.panel_height_m, request.antenna_height_m))
    # geometry() may read an existing arbitrary-coordinate cache, but must not
    # start scanning terrain merely because someone opens this view.
    if not hasattr(terrain, "profiles"):
        identity = {"method_version": METHOD_VERSION, "site": terrain.site,
                    "datasets": terrain.provenance(), "heights": sorted(heights),
                    "scan_radii_m": [400000, 300000], "az_steps_deg": [.125, .25]}
        if not (pipeline.root / "geometry" / digest(identity) / "receipt.json").is_file():
            raise DomainError("HORIZON_NOT_PREPARED", 409)
    fine, _, _, receipt = pipeline.geometry(terrain, heights, lambda _: None)
    return fine, receipt


def profile_view(request, pipeline):
    request = request.resolved()
    with pipeline.terrain(request) as terrain:
        profiles, receipt = _profiles(request, pipeline, terrain)
        output = []
        for height, frame in sorted(profiles.items()):
            points = []
            for row in frame.itertuples():
                value = float(row.horizon_deg)
                points.append({"azimuth_deg": float(row.az_deg),
                    "horizon_deg": value if math.isfinite(value) else None,
                    "coverage_complete": bool(row.coverage_complete) and math.isfinite(value),
                    "blocker_distance_m": float(row.blocker_distance_m) if math.isfinite(float(row.blocker_distance_m)) else None})
            output.append({"height_m": height, "azimuth_step_deg": float(frame.az_step_deg.iloc[0]),
                "points": points, "coverage_complete": all(p["coverage_complete"] for p in points)})
        return {"method_version": VERSION, "coordinate": terrain.site, "profiles": output,
            "source_sha256": digest(receipt), "scan_radius_m": 400000,
            "scope": "Cached terrain horizon at the requested hardware heights; no new mission validation."}


def sky_track(request, pipeline, chunk_index=0):
    request = request.resolved()
    provider = pipeline.shared_ephemeris
    source = provider.identity()
    # Resolve actual DEM elevation even for a point that has no horizon yet.
    with pipeline.terrain(request) as terrain:
        site, datasets = terrain.site, terrain.provenance()
    mission_start, mission_end = pd.Timestamp(request.start_utc), pd.Timestamp(request.end_utc)
    chunk_duration = pd.Timedelta(days=TRACK_CHUNK_DAYS)
    chunk_count = math.ceil((mission_end-mission_start)/chunk_duration)
    if chunk_index < 0 or chunk_index >= chunk_count:
        raise DomainError("OUTSIDE_SKY_TRACK", 409)
    start = mission_start + chunk_index*chunk_duration
    end = min(mission_end, start+chunk_duration)
    step = 300 if request.duration_hours <= 7*24 else 3600
    identity = {"version": VERSION, "ephemeris": source, "site": site, "datasets": datasets,
        "heights_m": [request.panel_height_m, request.antenna_height_m],
        "start_utc": start.isoformat(), "end_utc": end.isoformat(), "step_seconds": step}
    path = pipeline.root / "sky-tracks" / f"{digest(identity)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(path.with_suffix(".lock"))):
        if path.is_file():
            try:
                cached = json.loads(path.read_text())
                if cached["identity"] != identity or cached["sha256"] != digest(cached["payload"]):
                    raise ValueError("Sky track identity/checksum mismatch")
                return {**cached["payload"], "chunk_index": chunk_index, "chunk_count": chunk_count}
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise DomainError("SKY_TRACK_INTEGRITY_FAILED", 503) from error
        times = pd.date_range(start, end, freq=f"{step}s")
        if times[-1] != end:
            times = times.append(pd.DatetimeIndex([end]))
        count = len(times)
        # Checked reusable hourly vectors; no full-mission series or analysis.
        vectors, tables = provider.vectors(times, source)
        bodies = {}
        for body, target, height, radius in (("sun", 10, request.panel_height_m, 695700.),
                                             ("earth", 399, request.antenna_height_m, 6378.137)):
            az, el, distance = provider.topocentric(vectors, site, height, target)
            if not np.isfinite(np.column_stack([az, el, distance])).all() or (distance <= radius).any():
                raise DomainError("INVALID_SKY_TRACK", 503)
            bodies[body] = np.column_stack([az, el, np.rad2deg(np.arcsin(radius/distance))]).tolist()
        result = {"method_version": VERSION, "start_utc": start.isoformat(), "end_utc": end.isoformat(),
            "sampling_seconds": step, "sample_count": count,
            "render_mode": "line",
            "bodies": bodies, "source_sha256": digest(source), "tables": tables,
            "scope": "Progressive whole-mission sky track. Checked hourly SPICE interpolation, 5-minute display sampling for missions up to 7 days and hourly otherwise. Includes end boundary; no visibility duration or requirement decision."}
        atomic_json(path, {"identity": identity, "payload": result, "sha256": digest(result)})
        return {**result, "chunk_index": chunk_index, "chunk_count": chunk_count}
