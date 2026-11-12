"""Small exact-grid range aggregates; no native timeline scan on a warm query.

Daily leaves retain sums and prefix/suffix/maximum run lengths. Merging these
preserves runs crossing midnight, missing-evidence bounds and partial solar discs.
Queries outside indexed boundaries fall back to the native pipeline.
"""
from functools import lru_cache
import io
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.errors import DomainError
from app.mission.evaluation import metrics
from app.mission.metrics import validate_metrics
from app.services.lunarsight.acquire import hashfile

VERSION = "daily-native-metrics-2"


def pack(boundaries, leaves, chart_boundaries, chart_increments, chart_counts):
    """Combine daily/hourly summaries without retaining their native frames."""
    size = 1 << (len(leaves)-1).bit_length()
    tree = np.zeros((2*size, 26))
    tree[size:size+len(leaves)] = leaves
    for i in range(size-1, 0, -1):
        tree[i] = merge(tree[2*i], tree[2*i+1])
    stream = io.BytesIO()
    np.savez_compressed(stream, boundaries=boundaries, tree=tree, size=np.array(size),
        chart_boundaries=chart_boundaries,
        chart_prefix=np.vstack([np.zeros(6), np.cumsum(chart_increments, axis=0)]),
        chart_offsets=np.r_[0, np.cumsum(chart_counts)])
    return stream.getvalue(), node_metrics(tree[1])


def combine_parts(parts):
    """Join contiguous prepared parts; run lengths merge across every boundary."""
    days, leaves, hours, increments, counts = [], [], [], [], []
    previous = None
    for content in parts:
        with np.load(io.BytesIO(content), allow_pickle=False) as data:
            boundary, hourly = data["boundaries"], data["chart_boundaries"]
            if (len(boundary) < 2 or boundary[0] != hourly[0] or boundary[-1] != hourly[-1]
                    or (previous is not None and boundary[0] != previous)):
                raise ValueError("Prepared metric parts are not contiguous")
            size = int(data["size"])
            days.append(boundary[:-1])
            leaves.append(data["tree"][size:size+len(boundary)-1].copy())
            hours.append(hourly[:-1])
            increments.append(np.diff(data["chart_prefix"], axis=0))
            counts.append(np.diff(data["chart_offsets"]))
            previous = boundary[-1]
    if previous is None:
        raise ValueError("No metric parts")
    return pack(np.r_[np.concatenate(days), previous], np.concatenate(leaves),
        np.r_[np.concatenate(hours), previous], np.concatenate(increments), np.concatenate(counts))


def node_metrics(node):
    clamp = lambda values: [min(float(node[0]), max(0., round(float(v), 12))) for v in values]
    return {"total_sun_hours": clamp(node[1:3]), "total_earth_los_hours": clamp(node[3:5]),
        "longest_dark_hours": clamp(node[7:25].reshape(6, 3)[0:2, 2]),
        "longest_blackout_hours": clamp(node[7:25].reshape(6, 3)[2:4, 2]),
        "longest_joint_hours": clamp(node[7:25].reshape(6, 3)[4:6, 2])}


def merge(a, b):
    out = a+b
    ar, br, cr = a[7:25].reshape(6, 3), b[7:25].reshape(6, 3), out[7:25].reshape(6, 3)
    cr[:, 0] = np.where(ar[:, 0] == a[0], a[0]+br[:, 0], ar[:, 0])
    cr[:, 1] = np.where(br[:, 1] == b[0], b[0]+ar[:, 1], br[:, 1])
    cr[:, 2] = np.maximum(np.maximum(ar[:, 2], br[:, 2]), ar[:, 1]+br[:, 0])
    return out


def build(frame):
    # Validate continuity and fraction bounds using the authoritative engine.
    full_metrics = metrics(frame)
    starts = frame.start_utc.to_numpy(dtype="datetime64[us]")
    ends = frame.end_utc.to_numpy(dtype="datetime64[us]")
    dt = (ends-starts)/np.timedelta64(1, "h")
    sun, earth, joint = [frame[body+"_state"].to_numpy() for body in ("sun", "earth", "joint")]
    fraction = [frame[f"sun_visible_fraction_{bound}"].to_numpy() for bound in ("lower", "upper")] if "sun_visible_fraction_lower" in frame else [sun == "V", sun != "B"]
    values = [*fraction, earth == "V", earth != "B", joint == "V", joint != "B"]
    runs = [sun == "B", sun != "V", earth == "B", earth != "V", joint == "V", joint != "B"]
    days = starts.astype("datetime64[D]")
    edges = np.r_[0, np.flatnonzero(days[1:] != days[:-1])+1, len(frame)]
    size = 1 << (len(edges)-2).bit_length()
    tree = np.zeros((2*size, 26))
    for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        node, durations = tree[size+i], dt[a:b]
        node[0], node[25] = durations.sum(), b-a
        node[1:7] = [np.dot(v[a:b], durations) for v in values]
        for mask, row in zip(runs, node[7:25].reshape(6, 3)):
            selected = mask[a:b]
            changes = np.flatnonzero(np.diff(np.r_[False, selected, False]))
            widths = [float(durations[x:y].sum()) for x, y in zip(changes[::2], changes[1::2])]
            if widths:
                row[:] = [widths[0] if selected[0] else 0., widths[-1] if selected[-1] else 0., max(widths)]
    for i in range(size-1, 0, -1):
        tree[i] = merge(tree[2*i], tree[2*i+1])
    boundaries = np.r_[starts[edges[:-1]], ends[-1:]].astype("datetime64[us]")
    # A separate hourly level keeps short missions detailed and long charts
    # bounded, without opening the large native artifact at request time.
    hours = starts.astype("datetime64[h]")
    chart_edges = np.r_[0, np.flatnonzero(hours[1:] != hours[:-1])+1, len(frame)]
    chart_boundaries = np.r_[starts[chart_edges[:-1]], ends[-1:]].astype("datetime64[us]")
    hourly = np.column_stack([np.add.reduceat(v*dt, chart_edges[:-1]) for v in values])
    chart_prefix = np.vstack([np.zeros(6), np.cumsum(hourly, axis=0)])
    stream = io.BytesIO()
    np.savez_compressed(stream, boundaries=boundaries, tree=tree, size=np.array(size),
        chart_boundaries=chart_boundaries, chart_prefix=chart_prefix, chart_offsets=chart_edges)
    return stream.getvalue(), full_metrics


@lru_cache(maxsize=32)
def _read(path, size, mtime, ctime, expected):
    if hashfile(Path(path)) != expected:
        raise DomainError("PHYSICAL_METRICS_INTEGRITY_FAILED", 503)
    with np.load(path, allow_pickle=False) as data:
        return data["boundaries"], data["tree"], int(data["size"])


@lru_cache(maxsize=16)
def _read_chart(path, size, mtime, ctime, expected):
    _read(path, size, mtime, ctime, expected)  # Shared checksum verification.
    with np.load(path, allow_pickle=False) as data:
        return data["chart_boundaries"], data["chart_prefix"], data["chart_offsets"]


def chart(path, stat, reference, start, end, limit=800):
    boundaries, prefix, offsets = _read_chart(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, reference["sha256"])
    left, right = int(np.searchsorted(boundaries, start)), int(np.searchsorted(boundaries, end))
    if right >= len(boundaries) or left >= right or boundaries[left] != start or boundaries[right] != end:
        raise ValueError("Chart boundaries do not match indexed coverage")
    edges = np.linspace(left, right, min(limit, right-left)+1, dtype=int)
    duration = (boundaries[edges[1:]]-boundaries[edges[:-1]])/np.timedelta64(1, "h")
    fractions = np.clip((prefix[edges[1:]]-prefix[edges[:-1]])/duration[:, None], 0., 1.)
    output = []
    for a, b, values in zip(edges[:-1], edges[1:], fractions):
        row = {"start_utc": pd.Timestamp(boundaries[a]).tz_localize("UTC").isoformat(),
            "end_utc": pd.Timestamp(boundaries[b]).tz_localize("UTC").isoformat(),
            "aggregated": True, "source_intervals": int(offsets[b]-offsets[a])}
        for i, body in enumerate(("sun", "earth", "joint")):
            lo, hi = float(values[2*i]), max(float(values[2*i]), float(values[2*i+1]))
            row[body+"_visible_fraction_lower"], row[body+"_visible_fraction_upper"] = lo, hi
            row[body+"_state"] = "B" if hi == 0 else "V" if lo >= 1-1e-12 else "?"
            if body == "sun":
                row["sun_visible_fraction"] = lo if abs(hi-lo) < 1e-12 else None
        output.append(row)
    return output


def query(directory, reference, start, end):
    if reference.get("version") != VERSION:
        return None
    path = Path(directory)/"metrics.npz"
    try:
        stat = path.stat()
        boundaries, tree, size = _read(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, reference["sha256"])
        a, b = [pd.Timestamp(t).tz_convert("UTC").tz_localize(None).to_datetime64().astype("datetime64[us]") for t in (start, end)]
        left, right = int(np.searchsorted(boundaries, a)), int(np.searchsorted(boundaries, b))
        if left >= right or right >= len(boundaries) or boundaries[left] != a or boundaries[right] != b:
            return None
        first, last = np.zeros(26), np.zeros(26)
        left, right = left+size, right+size
        while left < right:
            if left & 1:
                first, left = merge(first, tree[left]), left+1
            if right & 1:
                right -= 1
                last = merge(tree[right], last)
            left, right = left//2, right//2
        node = merge(first, last)
        clamp = lambda values: [min(float(node[0]), max(0., round(float(v), 12))) for v in values]
        result = node_metrics(node)
        if a == boundaries[0] and b == boundaries[-1]:
            result = reference["full_metrics"]
        validate_metrics(result, float(node[0]))
        timeline = chart(path, stat, reference, a, b)
        return {"metrics_hours": result, "joint_hours": clamp(node[5:7]), "source_intervals": int(node[25]),
            "timeline": timeline, "timeline_transport": {"mode": "aggregated", "source_intervals": int(node[25]),
                "display_intervals": len(timeline), "exact_intervals_ready": False, "base_resolution_minutes": 60,
                "scope": "Duration-weighted hourly preview, at most 800 display bins; not exact instant evidence."}}
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        raise DomainError("PHYSICAL_METRICS_INTEGRITY_FAILED", 503) from error
