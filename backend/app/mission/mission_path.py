"""Mission requirement bounds across sampled numerical configurations.

These empirical envelopes do not bound physical DEM uncertainty or unsampled
continuous-time events. Full-horizon validation diagnostics remain unchanged.
"""
import numpy as np
import pandas as pd

from app.services.lunarsight.visibility import lookup
from app.services.lunarsight.durations import combine
from .evaluation import TOLERANCES, metrics, constraint_checks, decision, contact_evidence

VERSION = "sampled-mission-path-envelope-3.1"


def validate_mission_path(request, validation, base, fine, shorter, ephemerides, *, numerical=None, publish=None):
    result = {"passed": False, "policy_version": VERSION,
        "scope": "requested_sampled_sun_and_earth_paths_only",
        "tolerance_status": "PROVISIONAL", "targets": {},
        "limitations": ["Empirical numerical envelope; not a bound on physical DEM uncertainty or unsampled events.",
                        "Full-circle horizon validation remains unchanged."]}
    reasons, diagnostics = validation.get("reason_codes", []), validation.get("sensitivity", {})
    # Missing data, source integrity, ENU and seams remain blocking even when
    # numerical envelope evidence was prepared by an earlier request.
    if not reasons or not all(reason.endswith(":SENSITIVITY_FAILED") and
                              reason.rsplit(":", 1)[0] in diagnostics for reason in reasons):
        result["reason"] = "GLOBAL_FAILURE_NOT_NUMERICAL_ONLY"
        return result
    if numerical is None:
        inputs = ephemerides() if callable(ephemerides) else ephemerides
        numerical = path_evidence(request, validation, base, fine, shorter, inputs)
        if publish is not None:
            publish(numerical)
    for label, target in numerical["targets"].items():
        required = ((request.min_sunlit_fraction or 0) > 0 if label == "sun" else
                    (request.min_earth_los_fraction or 0) > 0 or request.contact_requirements is not None)
        result["targets"][label] = {**target, "required_for_decision": required}
    if "reason" in numerical:
        result["reason"] = numerical["reason"]
        return result
    metric = numerical["metrics_hours"]
    checks = constraint_checks(metric, request, contact_evidence=numerical["contact_evidence"])
    result.update(metrics_hours=metric, constraint_checks=checks,
                  bounded_decision=decision(checks.values()) if checks else None)
    result["passed"] = result["bounded_decision"] == "PASS"
    result["reason"] = "ROBUST_REQUIREMENT_BOUNDS" if result["passed"] else "REQUIREMENT_BOUNDS_NOT_CONCLUSIVE"
    return result


def path_evidence(request, validation, base, fine, shorter, ephemerides):
    """Threshold-independent empirical envelope, including exact Earth runs."""
    result = {"targets": {}}
    spatial = [d for name, d in validation["sensitivity"].items() if not name.startswith("time_")]
    sun, earth, sun1, earth1 = ephemerides[:4]
    index = sun1.index
    frame = pd.DataFrame(index=index)
    complete = True
    for label, height, coarse, native in (("sun", request.panel_height_m, sun, sun1),
                                          ("earth", request.antenna_height_m, earth, earth1)):
        differences = [d.get("angles_by_height", {}).get(str(height), {}).get("max_abs_deg") for d in spatial]
        if not differences or any(v is None or not np.isfinite(v) for v in differences):
            result["reason"] = "ANGULAR_EVIDENCE_MISSING"
            return result
        delta = max(differences)
        padding = delta + TOLERANCES["horizon_deg"]
        all_above, all_below, margins, spreads = [], [], [], []
        for grid_number, grid in enumerate((coarse.reindex(index, method="ffill"), native)):
            profiles = [lookup(p[height], grid.az_deg) for p in (base, fine, shorter)]
            horizons = np.stack([h for h, _ in profiles])
            covered = np.stack([c for _, c in profiles]).all(axis=0)
            elevation = grid.el_deg.to_numpy()
            valid = (grid.row_present.fillna(False).eq(True).to_numpy() & covered &
                     np.isfinite(elevation) & np.isfinite(horizons).all(axis=0))
            complete &= bool(valid.all())
            above = elevation - horizons.max(axis=0) - padding
            below = horizons.min(axis=0) - elevation - padding
            if label == "sun" and request.illumination_model == "solar_disc":
                from app.services.lunarsight.solar_disc import fractions, SUN_RADIUS_KM, EARTH_RADIUS_KM
                from app.services.lunarsight.shared_ephemeris import ANGLE_TOLERANCE_DEG
                other = earth.reindex(index, method="ffill") if grid_number == 0 else earth1
                lower, upper = [], []
                for group in (base, fine, shorter):
                    profile = group[height]
                    # Full/zero disk proofs only. Partial disks stay [0,1] in
                    # this conservative mission-path override, never centre V.
                    lo, _ = fractions(grid, other, profile.assign(horizon_deg=profile.horizon_deg+padding))
                    _, hi = fractions(grid, other, profile.assign(horizon_deg=profile.horizon_deg-padding))
                    lower.append(lo)
                    upper.append(hi)
                sr = np.rad2deg(np.arcsin(SUN_RADIUS_KM/grid.distance_km.to_numpy()))
                er = np.rad2deg(np.arcsin(EARTH_RADIUS_KM/other.distance_km.to_numpy()))
                separation = np.hypot(((other.az_deg.to_numpy()-grid.az_deg.to_numpy()+180)%360-180)
                                     *np.cos(np.deg2rad(elevation)), other.el_deg.to_numpy()-elevation)
                eclipse_clear = separation > sr+er+2*ANGLE_TOLERANCE_DEG
                all_above.append(valid & eclipse_clear & (np.min(lower, axis=0) >= 1-1e-12))
                all_below.append(valid & (np.max(upper, axis=0) <= 0))
            else:
                all_above.append(valid & (above > 0))
                all_below.append(valid & (below > 0))
            margins.extend(np.maximum(above, below).tolist())
            spreads.extend(np.ptp(horizons, axis=0).tolist())
        state = np.where(np.stack(all_above).all(axis=0), "V",
                         np.where(np.stack(all_below).all(axis=0), "B", "?"))
        frame[label + "_state"] = state
        if label == "sun" and request.illumination_model == "solar_disc":
            frame["sun_visible_fraction_lower"] = (state == "V").astype(float)
            frame["sun_visible_fraction_upper"] = (state != "B").astype(float)
        finite = bool(np.isfinite(margins).all() and np.isfinite(spreads).all())
        result["targets"][label] = {"height_m": height,
            "state": str(state[0]) if len(set(state)) == 1 else "MIXED",
            "native_sample_counts_5min_1min": [len(coarse), len(native)],
            "state_counts_1min": {s: int((state[:-1] == s).sum()) for s in ("V", "B", "?")},
            "max_path_horizon_spread_deg": float(max(spreads)) if finite else None,
            "global_discrepancy_deg": delta, "envelope_padding_deg": padding,
            "min_clearance_beyond_envelope_deg": float(min(margins)) if finite else None}
    if not complete:
        result["reason"] = "PATH_EVIDENCE_INCOMPLETE"
        return result
    frame["joint_state"] = combine(frame.sun_state, frame.earth_state)
    frame["start_utc"] = index
    frame["end_utc"] = index.to_series().shift(-1)
    intervals = frame.iloc[:-1]
    metric = metrics(intervals)
    result.update(metrics_hours=metric, contact_evidence=contact_evidence(intervals))
    return result
