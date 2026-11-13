"""Authoritative sampled-timeline evaluation for coordinate and snapshot evidence."""
import json

import numpy as np
import pandas as pd

from app.core.errors import DomainError
from app.services.lunarsight.contact_windows import analyze_contacts
from app.services.lunarsight.decision_policy import gated_decision
from app.services.lunarsight.durations import bounds
from app.services.lunarsight.visibility import sensitivity, lookup, SENSITIVITY_VERSION
from .metrics import hard_checks, assess_soft, validate_metrics

EVALUATION_VERSION = "mission-evaluation-2.1.0"
VALIDATION_VERSION = "mission-validation-1.0"
REQUIRED_COMPARISONS = ("azimuth_0.25_vs_0.125", "radius_400km_vs_300km", "time_5min_vs_1min")
TOLERANCES = {"horizon_deg": .1, "event_minutes": 5, "duration_minutes": 10}

def serialization_frame(frame):
    """Format UTC columns in NumPy, without boxing millions of Timestamps."""
    output = frame.copy(deep=False)
    for name in frame.columns:
        column = frame[name]
        if pd.api.types.is_datetime64_any_dtype(column.dtype):
            values = np.datetime_as_string(column.to_numpy(dtype="datetime64[ms]"), unit="ms", timezone="UTC")
            output[name] = np.where(column.isna(), None, values)
    return output


def records(frame):
    return json.loads(serialization_frame(frame).to_json(orient="records", date_format="iso"))


def metrics(frame):
    if (frame.empty or frame.start_utc.isna().any() or frame.end_utc.isna().any()
            or (frame.end_utc <= frame.start_utc).any()
            or not np.array_equal(frame.start_utc.iloc[1:].to_numpy(dtype="datetime64[us]"),
                                  frame.end_utc.iloc[:-1].to_numpy(dtype="datetime64[us]"))):
        raise DomainError("INCOMPLETE_TIMELINE", 409)
    duration = (frame.end_utc - frame.start_utc).dt.total_seconds().to_numpy() / 3600
    result = bounds(frame.sun_state, frame.earth_state, duration)
    if "sun_visible_fraction_lower" in frame:
        fractions = frame[["sun_visible_fraction_lower", "sun_visible_fraction_upper"]].to_numpy(dtype=float)
        if (not np.isfinite(fractions).all() or (fractions < 0).any() or (fractions > 1).any()
                or (fractions[:, 0] > fractions[:, 1]).any()):
            raise DomainError("INVALID_SOLAR_FRACTION_BOUNDS", 409)
        # Compatibility key: these are equivalent full-disc hours, not hours
        # when any part or the centre of the Sun was visible.
        result["total_sun_hours"] = (fractions*duration[:, None]).sum(axis=0).tolist()
    hours = float((frame.end_utc.iloc[-1] - frame.start_utc.iloc[0]).total_seconds() / 3600)
    validate_metrics(result, hours)
    # Clamp only sub-tolerance floating point accumulation (e.g. 72+2e-13).
    return {key: [min(hours, max(0., round(value, 12))) for value in pair] for key, pair in result.items()}


def constraint_checks(metric, request, frame=None, *, contact_evidence=None):
    checks = hard_checks(metric, request.min_sunlit_fraction or 0,
                        request.min_earth_los_fraction or 0, request.duration_hours)
    checks = {key: value for key, value in checks.items() if getattr(request, key) is not None}
    if request.contact_requirements is not None:
        if frame is None and contact_evidence is None:
            raise DomainError("ENGINE_CONTRACT_ERROR", 502)
        contact = frame_contacts(request, frame, evidence=contact_evidence)
        checks.update({"contact." + key: value for key, value in contact["requirements"]["sampled_checks"].items()})
    return checks


def decision(checks):
    checks = list(checks)
    return "FAIL" if "FAIL" in checks else "PASS" if all(c == "PASS" for c in checks) else "INDETERMINATE"


def events(frame):
    output = []
    for key in ("sun_state", "earth_state", "joint_state"):
        state = frame[key].to_numpy()
        starts = np.r_[0, np.flatnonzero(state[1:] != state[:-1]) + 1] if len(state) else []
        for a, b in zip(starts, [*starts[1:], len(state)]):
            output.append({"target": key.removesuffix("_state"), "state": str(state[a]),
                           "start_utc": frame.start_utc.iloc[a].isoformat(),
                           "end_utc": frame.end_utc.iloc[b-1].isoformat()})
    return output


def contact_evidence(frame):
    state = frame.earth_state.to_numpy()
    starts = np.r_[0, np.flatnonzero(state[1:] != state[:-1]) + 1]
    return {"intervals": [[frame.start_utc.iloc[a].isoformat(), frame.end_utc.iloc[b-1].isoformat(), str(state[a])]
                          for a, b in zip(starts, [*starts[1:], len(state)])],
            "step_minutes": float((frame.end_utc-frame.start_utc).dt.total_seconds().max()/60)}


def frame_contacts(request, frame, payload=None, *, evidence=None):
    """Losslessly coalesce Earth-state runs before contact analysis.

    Preserve the native source step separately. This avoids serializing and
    parsing every timestamp repeatedly during sensitivity checks.
    """
    evidence = contact_evidence(frame) if evidence is None else evidence
    intervals = [(pd.Timestamp(a), pd.Timestamp(b), state) for a, b, state in evidence["intervals"]]
    step = evidence["step_minutes"]
    payload = payload if payload is not None else {"request": request.model_dump(), "end_utc": request.end_utc}
    return analyze_contacts(payload, _normalized=(intervals, pd.Timestamp(request.start_utc), pd.Timestamp(request.end_utc), step),
                            **request.contact_requirements.model_dump())


def angle_difference(base, alternative):
    angles = {}
    for height, target in alternative.items():
        old, _ = lookup(base[height], target.az_deg)
        delta = abs(old - target.horizon_deg.to_numpy())
        finite = delta[np.isfinite(delta)]
        angles[str(height)] = {"comparable": len(finite),
            "max_abs_deg": float(finite.max()) if len(finite) else None}
    return angles


def numerical_evidence(frame, alternatives):
    """Threshold-independent metrics, event comparisons and lossless Earth runs."""
    metric = metrics(frame)
    comparisons = {}
    for name, variant in alternatives.items():
        if variant is None:
            continue  # Snapshot comparisons may explicitly lack coverage.
        other = metrics(variant)
        comparisons[name] = {"metrics_hours": other,
            "duration_delta_minutes": {key: [abs(a-b)*60 for a, b in zip(metric[key], other[key])] for key in metric},
            "temporal": sensitivity(frame, variant, ["sun_state", "earth_state", "joint_state"]),
            "contact_evidence": contact_evidence(variant)}
    return {"metrics_hours": metric, "comparisons": comparisons}


def validate(request, frame, alternatives, angles, *, terrain_complete,
             ephemeris_complete, seams, references, evidence_checks=(),
             azimuth_comparison_name="azimuth_0.25_vs_0.125", include_soft=True, numerical=None):
    """Missing comparisons fail closed, regardless of nominal feasibility."""
    numerical = numerical_evidence(frame, alternatives) if numerical is None else numerical
    metric = numerical["metrics_hours"]
    checks = constraint_checks(metric, request, frame)
    diagnostics = {}
    reasons = []
    for name in (azimuth_comparison_name, *REQUIRED_COMPARISONS[1:]):
        comparison = numerical["comparisons"].get(name)
        if comparison is None:
            diagnostics[name] = {"passed": False, "reason": "COMPARISON_EVIDENCE_MISSING"}
            reasons.append(name + ":COMPARISON_EVIDENCE_MISSING")
            continue
        other = comparison["metrics_hours"]
        variant_checks = constraint_checks(other, request, contact_evidence=comparison["contact_evidence"])
        deltas = comparison["duration_delta_minutes"]
        temporal = comparison["temporal"]
        angle = angles.get(name, {})
        angle_pass = name == "time_5min_vs_1min" or bool(angle) and all(
            item["max_abs_deg"] is not None and item["max_abs_deg"] <= TOLERANCES["horizon_deg"]
            for item in angle.values())
        nonangular_passed = (max(max(values) for values in deltas.values()) <= TOLERANCES["duration_minutes"]
            and all(item["events_first"] == item["events_second"]
                    and item["matched_first_within_15min"] == item["events_first"]
                    and (item["max_matched_event_shift_minutes"] or 0) <= TOLERANCES["event_minutes"]
                    for item in temporal.values())
            and variant_checks == checks)
        passed = nonangular_passed and angle_pass
        diagnostics[name] = {"duration_delta_minutes": deltas, "temporal": temporal,
            "angles_by_height": angle, "constraint_checks": variant_checks,
            "metrics_hours": other, "soft_constraint_checks": assess_soft(other, request.constraints)[0] if include_soft else {},
            "nonangular_passed": bool(nonangular_passed), "passed": bool(passed)}
        if not passed:
            reasons.append(name + ":SENSITIVITY_FAILED")
    if not terrain_complete:
        reasons.append("INCOMPLETE_TERRAIN")
    if not ephemeris_complete:
        reasons.append("INCOMPLETE_EPHEMERIS")
    if not all(item.get("passed") is True for item in seams):
        reasons.append("DEM_SEAM_FAILED")
    if not references or not all(item.get("passed") is True for item in references.values()):
        reasons.append("ENU_REFERENCE_FAILED")
    for check in evidence_checks:
        if check.get("passed") is not True:
            reasons.append(check["code"])
    return {"passed": not reasons, "policy_version": VALIDATION_VERSION,
        "sensitivity_version": SENSITIVITY_VERSION, "tolerance_status": "PROVISIONAL",
        "tolerances": TOLERANCES, "reason_codes": reasons, "enu_reference": references,
        "seams": seams, "evidence_checks": list(evidence_checks), "sensitivity": diagnostics}


def evaluate(request, frame, validation, *, include_soft=True):
    """One decision policy; soft preferences never override hard requirements."""
    if frame.empty or (frame.start_utc.iloc[0] != pd.Timestamp(request.start_utc)
            or frame.end_utc.iloc[-1] != pd.Timestamp(request.end_utc)):
        raise DomainError("INCOMPLETE_TIMELINE", 409)
    if getattr(request, "illumination_model", "sun_center") == "solar_disc" and "sun_visible_fraction_lower" not in frame:
        raise DomainError("ILLUMINATION_MODEL_MISMATCH", 409)
    metric = metrics(frame)
    checks = constraint_checks(metric, request, frame)
    nominal = decision(checks.values()) if checks else None
    final = gated_decision(nominal, validation, checks=checks)
    soft, soft_violations = assess_soft(metric, request.constraints) if include_soft else ({}, [])
    result = {"metrics_hours": metric, "constraint_checks": checks,
        "nominal_sampled_decision": nominal, "decision": final,
        "soft_constraint_checks": soft, "soft_violations": soft_violations,
        "requirement_policy": "availability-and-contact-windows-v1" if request.contact_requirements else "availability-fractions-v1",
        "validation": validation}
    if request.contact_requirements is not None:
        result["contact_analysis"] = frame_contacts(request, frame, {"request": request.model_dump(),
            "end_utc": request.end_utc, "decision": final, "validation": validation})
    return result


