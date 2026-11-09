"""Read-only access to versioned LunarSight presentation data.

This adapter intentionally uses the Python standard library so the lightweight API can
serve the verified catalog without importing the scientific pipeline dependencies.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATASET_VERSION = "v0.2.0"
METHOD_VERSION = "catalog-api-0.1.0"


def repository_root() -> Path:
    """Locate the checkout from this module instead of relying on process cwd."""
    return Path(__file__).resolve().parents[4]


def processed_root() -> Path:
    return repository_root() / "data" / "processed" / "lunarsight" / DATASET_VERSION


def site_catalog() -> dict[str, Any]:
    path = processed_root() / "site_catalog.geojson"
    if not path.is_file():
        raise FileNotFoundError(f"Versioned site catalog is missing: {path}")
    catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog["provenance"] = {
        "dataset_version": DATASET_VERSION,
        "method_version": METHOD_VERSION,
        "source": str(path.relative_to(repository_root())),
    }
    catalog["warnings"] = [
        "Candidate points are demonstration pixels selected inside NASA ROI polygons; they are not landing certifications."
    ]
    return catalog


def _site_prefix(site_id: str) -> str:
    accepted = {"Site01_P1": "Site01", "Site04_P1": "Site04"}
    try:
        return accepted[site_id]
    except KeyError as error:
        raise ValueError(f"Unsupported site_id: {site_id}") from error


def site_timeline(site_id: str, max_points: int = 360) -> dict[str, Any]:
    """Return a bounded, display-ready sample of the versioned visibility intervals."""
    if not 24 <= max_points <= 1440:
        raise ValueError("max_points must be between 24 and 1440")
    prefix = _site_prefix(site_id)
    path = processed_root() / "visibility" / f"{prefix}_intervals.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Visibility intervals are missing: {path}")

    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    stride = max(1, (len(rows) + max_points - 1) // max_points)
    sampled = rows[::stride]
    fields = (
        "start_utc",
        "end_utc",
        "sun_el_deg",
        "sun_horizon_deg",
        "sun_state",
        "earth_el_deg",
        "earth_horizon_deg",
        "earth_state",
        "joint_state",
    )
    points = [{field: row.get(field) for field in fields} for row in sampled]
    return {
        "site_id": site_id,
        "dataset_version": DATASET_VERSION,
        "method_version": METHOD_VERSION,
        "source": str(path.relative_to(repository_root())),
        "original_interval_count": len(rows),
        "sample_stride": stride,
        "points": points,
        "warnings": [
            "PROVISIONAL scenario; visualization sampling must not be used to recompute mission metrics."
        ],
    }


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Expected timezone-aware UTC timestamp")
    return parsed.astimezone(timezone.utc)


def _numeric(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def site_analysis(site_id: str, at_utc: str) -> dict[str, Any]:
    """Look up the native interval and an exact supported 72-hour start."""
    prefix = _site_prefix(site_id)
    requested = _parse_utc(at_utc)
    visibility_path = processed_root() / "visibility" / f"{prefix}_intervals.csv"
    windows_path = processed_root() / "visibility" / f"{prefix}_windows.csv"
    if not visibility_path.is_file() or not windows_path.is_file():
        raise FileNotFoundError(f"Versioned analysis is incomplete for {site_id}")

    interval: dict[str, str] | None = None
    with visibility_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            start = _parse_utc(row["start_utc"])
            end = _parse_utc(row["end_utc"])
            if start <= requested < end:
                interval = row
                break

    if interval is None:
        return {
            "site_id": site_id,
            "at_utc": requested.isoformat().replace("+00:00", "Z"),
            "availability": "OUTSIDE_EPHEMERIS_RANGE",
            "dataset_version": DATASET_VERSION,
            "method_version": METHOD_VERSION,
            "warnings": ["No result is inferred beyond the versioned ephemeris range."],
        }

    exact_window: dict[str, str] | None = None
    with windows_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if _parse_utc(row["start_utc"]) == requested:
                exact_window = row
                break

    window_result = None
    if exact_window is not None:
        window_result = {
            "start_utc": exact_window["start_utc"],
            "end_utc": exact_window["end_utc"],
            "decision": exact_window["decision"],
            "darkness_constraint": exact_window["darkness_constraint"],
            "earth_constraint": exact_window["earth_constraint"],
            "total_sun_hours": [
                _numeric(exact_window["total_sun_hours_L"]),
                _numeric(exact_window["total_sun_hours_U"]),
            ],
            "longest_dark_hours": [
                _numeric(exact_window["longest_dark_hours_L"]),
                _numeric(exact_window["longest_dark_hours_U"]),
            ],
            "longest_blackout_hours": [
                _numeric(exact_window["longest_blackout_hours_L"]),
                _numeric(exact_window["longest_blackout_hours_U"]),
            ],
            "longest_joint_hours": [
                _numeric(exact_window["longest_joint_hours_L"]),
                _numeric(exact_window["longest_joint_hours_U"]),
            ],
        }
    return {
        "site_id": site_id,
        "at_utc": requested.isoformat().replace("+00:00", "Z"),
        "availability": "AVAILABLE",
        "scenario_status": interval["scenario_status"],
        "instant": {
            "start_utc": interval["start_utc"],
            "end_utc": interval["end_utc"],
            "sun": {
                "state": interval["sun_state"],
                "azimuth_deg": _numeric(interval["sun_az_deg"]),
                "elevation_deg": _numeric(interval["sun_el_deg"]),
                "horizon_deg": _numeric(interval["sun_horizon_deg"]),
                "clearance_deg": _numeric(interval["sun_clearance_deg"]),
                "coverage": interval["sun_coverage_flag"],
            },
            "earth": {
                "state": interval["earth_state"],
                "azimuth_deg": _numeric(interval["earth_az_deg"]),
                "elevation_deg": _numeric(interval["earth_el_deg"]),
                "horizon_deg": _numeric(interval["earth_horizon_deg"]),
                "clearance_deg": _numeric(interval["earth_clearance_deg"]),
                "coverage": interval["earth_coverage_flag"],
            },
            "joint_state": interval["joint_state"],
        },
        "window_72h": window_result,
        "dataset_version": DATASET_VERSION,
        "method_version": METHOD_VERSION,
        "provenance": {
            "visibility": str(visibility_path.relative_to(repository_root())),
            "windows": str(windows_path.relative_to(repository_root())),
        },
        "warnings": [
            "PROVISIONAL scenario; thresholds and scenario dates require mission-owner approval.",
            *([] if exact_window is not None else ["No 72-hour metric was substituted because this timestamp is not an exact 15-minute start-grid point."]),
        ],
    }


def coverage_summary() -> dict[str, Any]:
    root = processed_root()
    raw = repository_root() / "data" / "raw"
    terrain = [
        ("Site01_dem", raw / "Site01" / "Site01_final_adj_5mpp_surf.tif", 5),
        ("Site04_dem", raw / "Site04" / "Site04_final_adj_5mpp_surf.tif", 5),
        ("dem80", raw / "global" / "LDEM_80S_80MPP_ADJ.TIF", 80),
        ("dem240", raw / "global" / "LDEM_60S_240MPP_ADJ.TIF", 240),
    ]
    return {
        "dataset_version": DATASET_VERSION,
        "method_version": METHOD_VERSION,
        "supported_sites": ["Site01_P1", "Site04_P1"],
        "global_visualization": {
            "coverage": "global",
            "source": "NASA SVS CGI Moon Kit",
            "scientific_analysis": False,
        },
        "analysis": {
            "coverage": "candidate sites only",
            "available": root.is_dir(),
            "scientific_analysis": True,
        },
        "terrain_sampling": [
            {
                "dataset_id": dataset_id,
                "resolution_m": resolution,
                "available": path.is_file()
                and path.with_name(path.name + ".receipt.json").is_file(),
            }
            for dataset_id, path, resolution in terrain
        ],
        "warnings": [
            "The global texture and bump map are visualization assets, not the DEM used by the scientific engine.",
            "Arbitrary-point terrain sampling is elevation/mesh coverage, not a complete landing assessment.",
        ],
    }
