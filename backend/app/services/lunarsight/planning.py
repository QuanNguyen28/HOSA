"""Scenario-bound LunarSight comparison and export services.

The scientific pipeline writes immutable, versioned CSV products.  This module
turns those products into the exact MVP contract described in the project
proposal: two supported sites, a 15-minute start grid, a fixed 72-hour activity,
three-state evidence, constraint bounds and traceable blocking events.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from app.planning.metrics import hard_checks, assess_soft
from app.planning.models import Constraints

from .catalog import DATASET_VERSION, processed_root, repository_root
from .sensitivity import summarize as summarize_sensitivity


METHOD_VERSION = "planning-api-0.3.0"
SUPPORTED_SITES = {"Site01_P1": "Site01", "Site04_P1": "Site04"}
METRIC_FIELDS = (
    "total_sun_hours",
    "total_earth_los_hours",
    "longest_dark_hours",
    "longest_blackout_hours",
    "longest_joint_hours",
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Required configuration is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _scenario() -> dict[str, Any]:
    return _read_json(repository_root() / "manifests/lunarsight/config/scenario.json")


def _geometry() -> dict[str, Any]:
    return _read_json(repository_root() / "manifests/lunarsight/config/geometry_config.json")


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Expected a timezone-aware UTC timestamp")
    return parsed.astimezone(timezone.utc)


def _number(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _validate_threshold(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"UNSUPPORTED_CONFIG: {name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= 72:
        raise ValueError(f"UNSUPPORTED_CONFIG: {name} must be within [0,72]")
    return result


def _max_rule(bounds: list[float], threshold: float) -> str:
    lower, upper = bounds
    if upper <= threshold + 1e-9:
        return "PASS"
    if lower > threshold + 1e-9:
        return "FAIL"
    return "INDETERMINATE"


def scenarios() -> dict[str, Any]:
    scenario = _scenario()
    geometry = _geometry()
    start = _parse_utc(scenario["A_utc"])
    stop = _parse_utc(scenario["B_utc"])
    start_count = int((stop - start).total_seconds() / 60 / scenario["start_step_minutes"])
    return {
        "dataset_version": DATASET_VERSION,
        "method_version": METHOD_VERSION,
        "scenarios": [
            {
                **scenario,
                "start_count": start_count,
                "start_index_range": [0, start_count - 1],
                "device_heights_m": {
                    "sun_panel": geometry["panel_height_m"],
                    "earth_antenna": geometry["antenna_height_m"],
                },
                "constraints_editable": True,
                "hard_requirement_fields": ["min_sunlit_fraction", "min_earth_los_fraction"],
                "soft_preference_fields": ["max_darkness_hours", "max_earth_blackout_hours"],
                "default_rank_by": "total_earth_los_hours",
                "fixed_fields": [
                    "D_hours",
                    "model_step_minutes",
                    "start_step_minutes",
                    "device_heights_m",
                ],
            }
        ],
        "warnings": [
            "The scenario is provisional until G0 mission-owner thresholds and epoch are approved.",
            "Visibility models sampled Sun and Earth centres; results are not landing certification.",
        ],
    }


def site_profile(site_id: str, target: str = "sun") -> dict[str, Any]:
    if site_id not in SUPPORTED_SITES:
        raise ValueError(f"Unsupported site_id: {site_id}")
    if target not in {"sun", "earth"}:
        raise ValueError("target must be 'sun' or 'earth'")
    prefix = SUPPORTED_SITES[site_id]
    height = 1 if target == "sun" else 2
    path = processed_root() / "horizon" / f"{prefix}_h{height}_az0.25_r400000.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Horizon profile is missing: {path}")
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    points = [
        {
            "azimuth_deg": _number(row["az_deg"]),
            "horizon_deg": _number(row["horizon_deg"]),
            "blocker_distance_m": _number(row["blocker_distance_m"]),
            "blocker_elevation_m": _number(row["blocker_z_m"]),
            "blocker_longitude_e_deg": _number(row["blocker_lon_e_deg"]),
            "blocker_latitude_deg": _number(row["blocker_lat_deg"]),
            "blocker_source": row["blocker_source"],
            "coverage_complete": row["coverage_complete"].lower() == "true",
        }
        for row in rows
    ]
    return {
        "site_id": site_id,
        "target": target,
        "observer_height_m": height,
        "azimuth_step_deg": 0.25,
        "scan_radius_m": 400_000,
        "coverage_complete": all(point["coverage_complete"] for point in points),
        "points": points,
        "dataset_version": DATASET_VERSION,
        "method_version": METHOD_VERSION,
        "provenance": {"source": str(path.relative_to(repository_root()))},
    }


def _window_row(site_id: str, start_index: int) -> tuple[Path, dict[str, str]]:
    prefix = SUPPORTED_SITES[site_id]
    path = processed_root() / "visibility" / f"{prefix}_windows.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Window analysis is missing: {path}")
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if int(row["start_index"]) == start_index:
                return path, row
    raise ValueError("UNSUPPORTED_CONFIG: start_index is outside the supported grid")


def _interval_rows(site_id: str, start: datetime, end: datetime) -> tuple[Path, list[dict[str, str]]]:
    prefix = SUPPORTED_SITES[site_id]
    path = processed_root() / "visibility" / f"{prefix}_intervals.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Visibility intervals are missing: {path}")
    selected: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            row_start = _parse_utc(row["start_utc"])
            row_end = _parse_utc(row["end_utc"])
            if row_start < end and row_end > start:
                selected.append(row)
    if not selected or _parse_utc(selected[0]["start_utc"]) > start or _parse_utc(selected[-1]["end_utc"]) < end:
        raise ValueError("DATA_NOT_READY: the 72-hour activity is not fully covered")
    for previous, current in zip(selected, selected[1:]):
        if previous["end_utc"] != current["start_utc"]:
            raise ValueError("DATA_NOT_READY: visibility intervals contain a gap")
    return path, selected


def _events(rows: list[dict[str, str]], body: str, activity_start: datetime, activity_end: datetime) -> list[dict[str, Any]]:
    state_field = f"{body}_state"
    events: list[dict[str, Any]] = []
    current: list[dict[str, str]] = []

    def finish() -> None:
        nonlocal current
        if not current:
            return
        start = max(activity_start, _parse_utc(current[0]["start_utc"]))
        end = min(activity_end, _parse_utc(current[-1]["end_utc"]))
        clearances = [(_number(row[f"{body}_clearance_deg"]), row) for row in current]
        finite = [(value, row) for value, row in clearances if value is not None]
        worst_value, worst = min(finite, key=lambda item: item[0]) if finite else (None, current[0])
        state_set = {row[state_field] for row in current}
        events.append(
            {
                "body": body,
                "state": "B" if state_set == {"B"} else "?",
                "start_utc": start.isoformat().replace("+00:00", "Z"),
                "end_utc": end.isoformat().replace("+00:00", "Z"),
                "duration_hours": (end - start).total_seconds() / 3600,
                "worst_sample": {
                    "at_utc": worst["start_utc"],
                    "azimuth_deg": _number(worst[f"{body}_az_deg"]),
                    "elevation_deg": _number(worst[f"{body}_el_deg"]),
                    "horizon_deg": _number(worst[f"{body}_horizon_deg"]),
                    "clearance_deg": worst_value,
                    "coverage_flag": worst[f"{body}_coverage_flag"],
                },
            }
        )
        current = []

    for row in rows:
        if row[state_field] != "V":
            if current and current[-1][state_field] != row[state_field]:
                finish()
            current.append(row)
        else:
            finish()
    finish()
    return events


def _decision(checks: dict[str, str]) -> str:
    values = list(checks.values())
    if "FAIL" in values:
        return "FAIL"
    if values and all(value == "PASS" for value in values):
        return "PASS"
    return "INDETERMINATE"


def _constraint_checks(metrics, min_sunlit_fraction, min_earth_los_fraction):
    return hard_checks(metrics, min_sunlit_fraction, min_earth_los_fraction)


def _site_result(
    site_id: str,
    start_index: int,
    preferences: Constraints,
    min_sunlit_fraction: float,
    min_earth_los_fraction: float,
) -> dict[str, Any]:
    window_path, row = _window_row(site_id, start_index)
    start = _parse_utc(row["start_utc"])
    end = _parse_utc(row["end_utc"])
    interval_path, intervals = _interval_rows(site_id, start, end)
    metrics = {
        metric: [_number(row[f"{metric}_L"]), _number(row[f"{metric}_U"])]
        for metric in METRIC_FIELDS
    }
    if any(value is None for pair in metrics.values() for value in pair):
        raise ValueError("DATA_NOT_READY: a metric bound is missing")
    typed_metrics = {key: [float(pair[0]), float(pair[1])] for key, pair in metrics.items()}
    evaluate = lambda values: _constraint_checks(values, min_sunlit_fraction, min_earth_los_fraction)
    checks = evaluate(typed_metrics)
    soft_checks, soft_violations = assess_soft(typed_metrics, preferences)
    geometry = _geometry()
    sensitivity = summarize_sensitivity(processed_root(), site_id, SUPPORTED_SITES[site_id], start, end,
        typed_metrics, evaluate, dict(site_id=site_id, start_utc=row["start_utc"], end_utc=row["end_utc"],
            constraints=preferences.model_dump(), min_sunlit_fraction=min_sunlit_fraction,
            min_earth_los_fraction=min_earth_los_fraction,
            device_heights_m={"sun_panel": geometry["panel_height_m"], "earth_antenna": geometry["antenna_height_m"]},
            duration_hours=72, model_step_minutes=5), geometry,
        soft_evaluate=lambda values: assess_soft(values, preferences)[0])
    events = _events(intervals, "sun", start, end) + _events(intervals, "earth", start, end)
    events.sort(key=lambda event: (-event["duration_hours"], event["start_utc"]))
    # A total-availability shortfall is explained by aggregate bounds, not a single event.
    decisive = None
    return {
        "site_id": site_id,
        "scenario_status": row["scenario_status"],
        "start_index": start_index,
        "start_utc": row["start_utc"],
        "end_utc": row["end_utc"],
        "metrics": typed_metrics,
        "constraint_states": checks,
        "soft_constraint_states": soft_checks,
        "soft_violations": soft_violations,
        "decision": _decision(checks),
        "decisive_event": decisive,
        "events": events,
        "sensitivity": sensitivity,
        "provenance": {
            "windows": str(window_path.relative_to(repository_root())),
            "intervals": str(interval_path.relative_to(repository_root())),
        },
    }


def _grid_summary(site_id: str, min_sunlit_fraction, min_earth_los_fraction) -> dict[str, Any]:
    prefix = SUPPORTED_SITES[site_id]
    path = processed_root() / "visibility" / f"{prefix}_windows.csv"
    counts = {"PASS": 0, "FAIL": 0, "INDETERMINATE": 0}
    passing: list[int] = []
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            metrics = {key: [float(row[f"{key}_{bound}"]) for bound in ("L", "U")] for key in METRIC_FIELDS}
            decision = _decision(_constraint_checks(metrics, min_sunlit_fraction, min_earth_los_fraction))
            counts[decision] += 1
            if decision == "PASS":
                passing.append(int(row["start_index"]))
    ranges: list[list[int]] = []
    for index in passing:
        if not ranges or index != ranges[-1][1] + 1:
            ranges.append([index, index])
        else:
            ranges[-1][1] = index
    return {"counts": counts, "passing_start_index_ranges": ranges}


def analyze_request(payload: dict[str, Any]) -> dict[str, Any]:
    scenario = _scenario()
    allowed_fields = {"scenario_id", "site_ids", "start_index", "constraints", "scan_grid", "min_sunlit_fraction", "min_earth_los_fraction"}
    unsupported_fields = sorted(set(payload) - allowed_fields)
    if unsupported_fields:
        raise ValueError(
            "UNSUPPORTED_CONFIG: immutable scenario fields or unknown inputs: "
            + ", ".join(unsupported_fields)
        )
    if payload.get("scenario_id") != scenario["scenario_id"]:
        raise ValueError("UNSUPPORTED_CONFIG: unknown scenario_id")
    site_ids = payload.get("site_ids")
    if not isinstance(site_ids, list) or not site_ids or len(site_ids) > 2 or len(set(site_ids)) != len(site_ids):
        raise ValueError("UNSUPPORTED_CONFIG: site_ids must contain one or two unique sites")
    if any(site_id not in SUPPORTED_SITES for site_id in site_ids):
        raise ValueError("UNSUPPORTED_CONFIG: unsupported site_id")
    start_index = payload.get("start_index")
    if isinstance(start_index, bool) or not isinstance(start_index, int) or not 0 <= start_index < 1344:
        raise ValueError("UNSUPPORTED_CONFIG: start_index must be an integer in [0,1344)")
    constraints = payload.get("constraints", {})
    if not isinstance(constraints, dict):
        raise ValueError("UNSUPPORTED_CONFIG: constraints are required")
    allowed_constraints = {"max_darkness_hours", "max_earth_blackout_hours"}
    unsupported_constraints = sorted(set(constraints) - allowed_constraints)
    if unsupported_constraints:
        raise ValueError(
            "UNSUPPORTED_CONFIG: unknown constraints: " + ", ".join(unsupported_constraints)
        )
    try:
        preferences = Constraints.model_validate(constraints)
    except ValueError as error:
        raise ValueError("UNSUPPORTED_CONFIG: invalid soft preferences") from error
    min_sun = payload.get("min_sunlit_fraction")
    min_earth = payload.get("min_earth_los_fraction")
    for name, value in (("min_sunlit_fraction", min_sun), ("min_earth_los_fraction", min_earth)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"UNSUPPORTED_CONFIG: {name} is required and must be within [0,1]")
    results = [_site_result(site_id, start_index, preferences, min_sun, min_earth) for site_id in site_ids]
    canonical_request = {
        "scenario_id": scenario["scenario_id"],
        "site_ids": site_ids,
        "start_index": start_index,
        "constraints": preferences.model_dump(),
        "scan_grid": bool(payload.get("scan_grid", False)),
        "min_sunlit_fraction": min_sun,
        "min_earth_los_fraction": min_earth,
    }
    result_id = hashlib.sha256(
        json.dumps(canonical_request, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]
    response: dict[str, Any] = {
        "schema_version": "2.0",
        "result_id": result_id,
        "request": canonical_request,
        "scenario": {
            "scenario_id": scenario["scenario_id"],
            "status": scenario["status"],
            "activity_duration_hours": scenario["D_hours"],
            "model_step_minutes": scenario["model_step_minutes"],
            "start_step_minutes": scenario["start_step_minutes"],
        },
        "sites": results,
        "overall_decision": _decision({result["site_id"]: result["decision"] for result in results}),
        "dataset_version": DATASET_VERSION,
        "method_version": METHOD_VERSION,
        "source_manifest": "manifests/lunarsight/source_manifest.json",
        "warnings": [
            "PROVISIONAL scenario: mission-owner thresholds and epoch have not passed G0 approval.",
            "Earth-centre line of sight is geometric visibility, not a radio link budget.",
            "Sun-centre visibility is not a photovoltaic or thermal model.",
        ],
    }
    if canonical_request["scan_grid"]:
        response["grid_summary"] = {
            site_id: _grid_summary(site_id, min_sun, min_earth) for site_id in site_ids
        }
    _persist_result(response)
    return response


def _result_dir() -> Path:
    return repository_root() / "data/cache/lunarsight/results"


def _persist_result(result: dict[str, Any]) -> None:
    directory = _result_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{result['result_id']}.json"
    temporary = directory / f".{result['result_id']}.{uuid4().hex}.tmp"
    try:
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            temporary.replace(target)
        except PermissionError:
            # Windows readers/scanners may briefly deny replacement. Retry only
            # the atomic rename, retaining this writer's unique temporary file.
            for attempt in range(5):
                time.sleep(.01 * (attempt + 1))
                try:
                    os.replace(temporary, target)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
    finally:
        temporary.unlink(missing_ok=True)


def load_result(result_id: str) -> dict[str, Any]:
    if len(result_id) != 20 or any(character not in "0123456789abcdef" for character in result_id):
        raise ValueError("Invalid result_id")
    path = _result_dir() / f"{result_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Analysis result not found: {result_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def result_csv(result: dict[str, Any]) -> str:
    columns = [
        "result_id",
        "scenario_id",
        "site_id",
        "start_index",
        "start_utc",
        "end_utc",
        "decision",
        "sunlight_requirement",
        "earth_los_requirement",
        "soft_darkness_preference",
        "soft_earth_blackout_preference",
        "max_darkness_hours",
        "max_earth_blackout_hours",
        "min_sunlit_fraction",
        "min_earth_los_fraction",
        "sensitivity_status",
        "sensitivity_scope_json",
        "total_sun_hours_L",
        "total_sun_hours_U",
        "total_earth_los_hours_L",
        "total_earth_los_hours_U",
        "longest_dark_hours_L",
        "longest_dark_hours_U",
        "longest_blackout_hours_L",
        "longest_blackout_hours_U",
        "longest_joint_hours_L",
        "longest_joint_hours_U",
        "dataset_version",
        "method_version",
    ]
    rows: list[dict[str, Any]] = []
    for site in result["sites"]:
        row = {
            "result_id": result["result_id"],
            "scenario_id": result["request"]["scenario_id"],
            "site_id": site["site_id"],
            "start_index": site["start_index"],
            "start_utc": site["start_utc"],
            "end_utc": site["end_utc"],
            "decision": site["decision"],
            "sunlight_requirement": site["constraint_states"]["min_sunlit_fraction"],
            "earth_los_requirement": site["constraint_states"]["min_earth_los_fraction"],
            "soft_darkness_preference": site["soft_constraint_states"].get("max_darkness_hours", ""),
            "soft_earth_blackout_preference": site["soft_constraint_states"].get("max_earth_blackout_hours", ""),
            "max_darkness_hours": result["request"]["constraints"]["max_darkness_hours"],
            "max_earth_blackout_hours": result["request"]["constraints"]["max_earth_blackout_hours"],
            "min_sunlit_fraction": result["request"].get("min_sunlit_fraction"),
            "min_earth_los_fraction": result["request"]["min_earth_los_fraction"],
            "sensitivity_status": site["sensitivity"]["status"],
            "sensitivity_scope_json": json.dumps(site["sensitivity"]["scope"], separators=(",", ":")),
            "dataset_version": result["dataset_version"],
            "method_version": result["method_version"],
        }
        for metric, pair in site["metrics"].items():
            row[f"{metric}_L"], row[f"{metric}_U"] = pair
        rows.append(row)
    from io import StringIO

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()

