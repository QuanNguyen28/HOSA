"""Bounded UI timelines and lossless, random-access native interval artifacts.

Aggregation is display-only. Metrics, requirements and validation always use
native frames. Mixed display bins are explicitly marked and are not instants.
"""
from functools import lru_cache
from pathlib import Path
import os
import tempfile

import numpy as np
import pandas as pd

from app.core.errors import DomainError
from app.mission.evaluation import records
from app.services.lunarsight.acquire import hashfile

VERSION = "progressive-point-3"
DISPLAY_POINTS = 800


def display_timeline(frame, limit=DISPLAY_POINTS):
    if len(frame) <= limit:
        return records(frame), {"mode": "native", "source_intervals": len(frame), "display_intervals": len(frame)}
    edges = np.linspace(0, len(frame), limit+1, dtype=int)
    duration = (frame.end_utc-frame.start_utc).dt.total_seconds().to_numpy()
    states = {body: frame[f"{body}_state"].to_numpy() for body in ("sun", "earth", "joint")}
    fractions = {}
    for body, state in states.items():
        fractions[body] = (frame[f"{body}_visible_fraction_lower"].to_numpy(),
                           frame[f"{body}_visible_fraction_upper"].to_numpy()) if f"{body}_visible_fraction_lower" in frame else (state == "V", state != "B")
    output = []
    for a, b in zip(edges[:-1], edges[1:]):
        dt = duration[a:b]
        width = float(dt.sum())
        row = {"start_utc": frame.start_utc.iloc[a].isoformat(), "end_utc": frame.end_utc.iloc[b-1].isoformat(),
               "aggregated": True, "source_intervals": int(b-a)}
        for body, state in states.items():
            values = state[a:b]
            row[f"{body}_state"] = str(values[0]) if (values == values[0]).all() else "?"
            lower, upper = [float(np.dot(value[a:b], dt)/width) for value in fractions[body]]
            row[f"{body}_visible_fraction_lower"] = lower
            row[f"{body}_visible_fraction_upper"] = upper
            if body == "sun":
                row["sun_visible_fraction"] = lower if abs(upper-lower) < 1e-12 else None
        output.append(row)
    return output, {"mode": "aggregated", "source_intervals": len(frame), "display_intervals": len(output),
                    "scope": "Duration-weighted display bins; use interval endpoint for exact native instants."}


def write_frame(path, frame):
    """Numeric/unicode structured NPY: mmap readable, never pickle."""
    columns, encodings = {}, {}
    for name, column in frame.items():
        if pd.api.types.is_datetime64_any_dtype(column.dtype):
            columns[name] = column.to_numpy(dtype="datetime64[us]")
        elif isinstance(column.dtype, pd.CategoricalDtype) or column.dtype.kind in "OUS":
            values = pd.Categorical(column.astype(str))
            columns[name] = values.codes
            encodings[name] = values.categories.tolist()
        else:
            columns[name] = column.to_numpy()
    array = np.empty(len(frame), dtype=[(name, value.dtype) for name, value in columns.items()])
    for name, value in columns.items():
        array[name] = value
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".npy.tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            np.save(handle, array, allow_pickle=False)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"file": path.name, "sha256": hashfile(path), "encodings": encodings}


@lru_cache(maxsize=32)
def _checked_hash(path, size, mtime, ctime):
    return hashfile(Path(path))


def read_array(directory, reference):
    path = Path(directory)/reference["file"]
    try:
        if reference["file"] not in {"timeline.npy", "preview.npy"}:
            raise ValueError("Invalid timeline artifact")
        stat = path.stat()
        if _checked_hash(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) != reference["sha256"]:
            raise ValueError("Timeline checksum mismatch")
        return np.load(path, allow_pickle=False, mmap_mode="r")
    except (OSError, ValueError, KeyError) as error:
        raise DomainError("TIMELINE_INTEGRITY_FAILED", 503) from error


def frame_from_array(array, reference=None):
    encodings = (reference or {}).get("encodings", {})
    frame = pd.DataFrame({name: pd.Categorical.from_codes(array[name], encodings[name])
                          if name in encodings else array[name] for name in array.dtype.names})
    for name in ("start_utc", "end_utc"):
        frame[name] = pd.to_datetime(frame[name], utc=True)
    for name in frame:
        if name.endswith("_state"):
            # Different windows may observe different subsets of V/B/?. Keep
            # the shared state alphabet for comparisons with freshly built frames.
            frame[name] = pd.Categorical(frame[name], categories=["V", "B", "?"])
    return frame


def exact_interval(directory, reference, at_utc):
    stamp = pd.Timestamp(at_utc)
    if stamp.tz is None or pd.isna(stamp):
        raise DomainError("INVALID_INTERVAL_TIME", 400)
    time = stamp.tz_convert("UTC").tz_localize(None).to_datetime64().astype("datetime64[us]")
    array = read_array(directory, reference)
    index = int(np.searchsorted(array["start_utc"], time, side="right"))-1
    if index < 0 or time >= array["end_utc"][index]:
        raise DomainError("OUTSIDE_MISSION_WINDOW", 409)
    return records(frame_from_array(array[index:index+1], reference))[0]


def full_timeline(directory, result):
    if result.get("timeline_transport", {}).get("mode") == "aggregated":
        reference = result["provenance"]["timeline_artifact"]
        frame = frame_from_array(read_array(directory, reference), reference)
        return {**result, "timeline": records(frame), "timeline_transport": {
            "mode": "native", "source_intervals": len(frame), "display_intervals": len(frame)}}
    return result
