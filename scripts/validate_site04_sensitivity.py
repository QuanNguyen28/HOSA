"""Reproduce Site04 azimuth/time-grid sensitivity from versioned products.

The one-minute Horizons case is an independent 72-hour query and is cached with
the same integrity contract as the main pipeline.  Run from the repository root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.lunarsight.horizons import fetch  # noqa: E402
from app.services.lunarsight.visibility import (  # noqa: E402
    analyze,
    grid_windows,
    lookup,
    sensitivity,
    visibility,
)


def read_ephemeris(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["utc"]).set_index("utc")
    frame.index = pd.DatetimeIndex(frame.index).tz_convert("UTC")
    frame["row_present"] = frame["row_present"].astype(bool)
    return frame


def read_profile(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["coverage_complete"] = frame["coverage_complete"].astype(bool)
    return frame


def main() -> None:
    processed = ROOT / "data/processed/lunarsight/v0.2.0"
    cache = ROOT / "data/cache/lunarsight/v0.2.0"
    report_path = ROOT / "docs/validation/lunarsight/v0.2.0/reports/Site04_sensitivity.json"
    catalog = json.loads((processed / "site_catalog.geojson").read_text(encoding="utf-8"))
    site = next(feature["properties"] for feature in catalog["features"] if feature["id"] == "Site04_P1")
    scenario = json.loads((ROOT / "manifests/lunarsight/config/scenario.json").read_text(encoding="utf-8"))
    geometry = json.loads((ROOT / "manifests/lunarsight/config/geometry_config.json").read_text(encoding="utf-8"))
    start = pd.Timestamp(scenario["A_utc"])
    stop = pd.Timestamp(scenario["B_utc"])
    boundary = pd.Timestamp(scenario["end_utc"])
    case_end = start + pd.Timedelta(hours=72)

    ephemeris_dir = processed / "ephemeris"
    sun_5 = read_ephemeris(next(ephemeris_dir.glob("Site04_P1_sun_5min_*.csv")))
    earth_5 = read_ephemeris(next(ephemeris_dir.glob("Site04_P1_earth_5min_*.csv")))
    if sun_5.index[-1] != boundary or earth_5.index[-1] != boundary:
        raise ValueError("Five-minute Site04 ephemeris does not include the scenario boundary")

    horizon_dir = processed / "horizon"
    profiles: dict[tuple[int, str], pd.DataFrame] = {}
    for height in (1, 2):
        profiles[(height, "base")] = read_profile(horizon_dir / f"Site04_h{height}_az0.25_r400000.csv")
        profiles[(height, "fine")] = read_profile(horizon_dir / f"Site04_h{height}_az0.125_r400000.csv")

    base = visibility(sun_5, earth_5, profiles[(1, "base")], profiles[(2, "base")])
    fine = visibility(sun_5, earth_5, profiles[(1, "fine")], profiles[(2, "fine")])
    constraints = scenario["example_constraints"]
    base_windows = grid_windows(
        base,
        start,
        stop,
        constraints["max_darkness_hours"],
        constraints["max_earth_blackout_hours"],
    )
    fine_windows = grid_windows(
        fine,
        start,
        stop,
        constraints["max_darkness_hours"],
        constraints["max_earth_blackout_hours"],
    )
    columns = ["sun_state", "earth_state", "joint_state"]
    angular: dict[str, dict[str, float | int | None]] = {}
    for height in (1, 2):
        fine_profile = profiles[(height, "fine")]
        base_angles, _ = lookup(profiles[(height, "base")], fine_profile.az_deg)
        differences = np.abs(base_angles - fine_profile.horizon_deg.to_numpy())
        differences = differences[np.isfinite(differences)]
        angular[str(height)] = {
            "comparable": int(len(differences)),
            "p95_abs_deg": float(np.percentile(differences, 95)),
            "max_abs_deg": float(differences.max()),
        }
    duration_delta = {
        column: float((fine_windows[column] - base_windows[column]).abs().max() * 60)
        for column in base_windows
        if column.endswith(("_L", "_U"))
    }
    azimuth_result = {
        "angles_by_height_m": angular,
        "temporal": sensitivity(base, fine, columns),
        "decisions_changed": int((fine_windows.decision != base_windows.decision).sum()),
        "max_duration_delta_minutes": duration_delta,
    }

    sun_1, sun_meta = fetch(
        cache,
        site,
        10,
        geometry["panel_height_m"],
        start,
        case_end,
        1,
        geometry["R_ref_m"],
        geometry["horizons_candidate_radius_m"],
    )
    earth_1, earth_meta = fetch(
        cache,
        site,
        399,
        geometry["antenna_height_m"],
        start,
        case_end,
        1,
        geometry["R_ref_m"],
        geometry["horizons_candidate_radius_m"],
    )
    one_minute = visibility(sun_1, earth_1, profiles[(1, "base")], profiles[(2, "base")])
    five_minute = base[base.end_utc <= case_end]
    bounds_5, checks_5, decision_5 = analyze(
        five_minute,
        start,
        constraints["max_darkness_hours"],
        constraints["max_earth_blackout_hours"],
    )
    bounds_1, checks_1, decision_1 = analyze(
        one_minute,
        start,
        constraints["max_darkness_hours"],
        constraints["max_earth_blackout_hours"],
    )
    bounds_delta = {
        key: [float(abs(left - right) * 60) for left, right in zip(bounds_5[key], bounds_1[key])]
        for key in bounds_5
    }
    time_result = {
        "case_start": str(start),
        "case_end": str(case_end),
        "temporal": sensitivity(five_minute, one_minute, columns),
        "decision_5min": decision_5,
        "decision_1min": decision_1,
        "constraint_states_5min": checks_5,
        "constraint_states_1min": checks_1,
        "bounds_abs_delta_minutes": bounds_delta,
        "raw_receipts": [sun_meta["raw_file"].replace(".json", ".receipt.json"), earth_meta["raw_file"].replace(".json", ".receipt.json")],
    }
    tolerance = {
        "horizon_deg": geometry["tol_horizon_deg"],
        "event_minutes": geometry["tol_event_minutes"],
        "duration_minutes": geometry["tol_duration_minutes"],
        "status": geometry["tol_status"],
    }
    azimuth_sensitive = bool(
        azimuth_result["decisions_changed"]
        or any((item["max_abs_deg"] or 0) > tolerance["horizon_deg"] for item in angular.values())
        or max(duration_delta.values()) > tolerance["duration_minutes"]
    )
    time_sensitive = bool(
        decision_5 != decision_1
        or max(max(pair) for pair in bounds_delta.values()) > tolerance["duration_minutes"]
        or any(
            (item["max_matched_event_shift_minutes"] or 0) > tolerance["event_minutes"]
            or item["events_first"] != item["events_second"]
            for item in time_result["temporal"].values()
        )
    )
    report = {
        "scenario_status": scenario["status"],
        "site_id": site["site_id"],
        "tolerance": tolerance,
        "azimuth_0.25_vs_0.125": {**azimuth_result, "sensitive": azimuth_sensitive},
        "time_5min_vs_1min": {**time_result, "sensitive": time_sensitive},
        "gate": "PASS" if not time_sensitive and azimuth_result["decisions_changed"] == 0 else "REVIEW",
        "limitations": [
            "No independent 300 km Site04 profile is present; scan-radius sensitivity is gated by the validated Site01 case.",
            "Tolerance approval remains provisional at G0.",
        ],
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(report_path.relative_to(ROOT))
    print(json.dumps({"gate": report["gate"], "azimuth_sensitive": azimuth_sensitive, "time_sensitive": time_sensitive}, indent=2))


if __name__ == "__main__":
    main()
