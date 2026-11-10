"""Authoritative sampled-timeline evaluation for coordinate and snapshot evidence."""
import json

import numpy as np
import pandas as pd

from app.core.errors import DomainError
from app.services.lunarsight.contact_windows import analyze_contacts
from app.services.lunarsight.durations import bounds
from app.services.lunarsight.visibility import sensitivity, lookup, SENSITIVITY_VERSION
from .metrics import hard_checks, assess_soft, validate_metrics

EVALUATION_VERSION = "mission-evaluation-1.0"
VALIDATION_VERSION = "mission-validation-1.0"
REQUIRED_COMPARISONS = ("azimuth_0.25_vs_0.125", "radius_400km_vs_300km", "time_5min_vs_1min")
TOLERANCES = {"horizon_deg": .1, "event_minutes": 5, "duration_minutes": 10}

def records(frame):
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def metrics(frame):
    if (frame.empty or frame.start_utc.isna().any() or frame.end_utc.isna().any()
            or (frame.end_utc <= frame.start_utc).any()
            or not np.array_equal(frame.start_utc.iloc[1:].to_numpy(), frame.end_utc.iloc[:-1].to_numpy())):
        raise DomainError("INCOMPLETE_TIMELINE", 409)
    duration = (frame.end_utc - frame.start_utc).dt.total_seconds().to_numpy() / 3600
    result = bounds(frame.sun_state, frame.earth_state, duration)
    hours = float((frame.end_utc.iloc[-1] - frame.start_utc.iloc[0]).total_seconds() / 3600)
    validate_metrics(result, hours)
    # Clamp only sub-tolerance floating point accumulation (e.g. 72+2e-13).
    return {key: [min(hours, max(0., round(value, 12))) for value in pair] for key, pair in result.items()}


def constraint_checks(metric, request, frame=None):
    checks = hard_checks(metric, request.min_sunlit_fraction or 0,
                        request.min_earth_los_fraction or 0, request.duration_hours)
    checks = {key: value for key, value in checks.items() if getattr(request, key) is not None}
    if request.contact_requirements is not None:
        if frame is None:
            raise DomainError("ENGINE_CONTRACT_ERROR", 502)
        contact = analyze_contacts({"request": request.model_dump(), "end_utc": request.end_utc,
            "timeline": records(frame[["start_utc", "end_utc", "earth_state"]])},
            **request.contact_requirements.model_dump())
        checks.update({"contact." + key: value for key, value in contact["requirements"]["sampled_checks"].items()})
    return checks


def decision(checks):
    checks = list(checks)
    return "FAIL" if "FAIL" in checks else "PASS" if all(c == "PASS" for c in checks) else "INDETERMINATE"


def events(frame):
    output = []
    for key in ("sun_state", "earth_state", "joint_state"):
        start, previous = None, None
        for row in frame.itertuples():
            state = getattr(row, key)
            if state != previous:
                if previous is not None:
                    output.append({"target": key.removesuffix("_state"), "state": previous,
                                   "start_utc": start.isoformat(), "end_utc": row.start_utc.isoformat()})
                start, previous = row.start_utc, state
        if previous is not None:
            output.append({"target": key.removesuffix("_state"), "state": previous,
                           "start_utc": start.isoformat(), "end_utc": frame.end_utc.iloc[-1].isoformat()})
    return output


def angle_difference(base, alternative):
    angles = {}
    for height, target in alternative.items():
        old, _ = lookup(base[height], target.az_deg)
        delta = abs(old - target.horizon_deg.to_numpy())
        finite = delta[np.isfinite(delta)]
        angles[str(height)] = {"comparable": len(finite),
            "max_abs_deg": float(finite.max()) if len(finite) else None}
    return angles


def validate(request, frame, alternatives, angles, *, terrain_complete,
             ephemeris_complete, seams, references, evidence_checks=()):
    """Missing comparisons fail closed, regardless of nominal feasibility."""
    metric = metrics(frame)
    checks = constraint_checks(metric, request, frame)
    diagnostics = {}
    reasons = []
    for name in REQUIRED_COMPARISONS:
        variant = alternatives.get(name)
        if variant is None:
            diagnostics[name] = {"passed": False, "reason": "COMPARISON_EVIDENCE_MISSING"}
            reasons.append(name + ":COMPARISON_EVIDENCE_MISSING")
            continue
        other = metrics(variant)
        variant_checks = constraint_checks(other, request, variant)
        deltas = {key: [abs(a-b)*60 for a, b in zip(metric[key], other[key])] for key in metric}
        temporal = sensitivity(frame, variant, ["sun_state", "earth_state", "joint_state"])
        angle = angles.get(name, {})
        angle_pass = name == "time_5min_vs_1min" or bool(angle) and all(
            item["max_abs_deg"] is not None and item["max_abs_deg"] <= TOLERANCES["horizon_deg"]
            for item in angle.values())
        passed = (max(max(values) for values in deltas.values()) <= TOLERANCES["duration_minutes"]
            and all(item["events_first"] == item["events_second"]
                    and item["matched_first_within_15min"] == item["events_first"]
                    and (item["max_matched_event_shift_minutes"] or 0) <= TOLERANCES["event_minutes"]
                    for item in temporal.values())
            and angle_pass and variant_checks == checks)
        diagnostics[name] = {"duration_delta_minutes": deltas, "temporal": temporal,
            "angles_by_height": angle, "constraint_checks": variant_checks,
            "metrics_hours": other, "soft_constraint_checks": assess_soft(other, request.constraints)[0],
            "passed": bool(passed)}
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


def evaluate(request, frame, validation):
    """One decision policy; soft preferences never override hard requirements."""
    if frame.empty or (frame.start_utc.iloc[0] != pd.Timestamp(request.start_utc)
            or frame.end_utc.iloc[-1] != pd.Timestamp(request.end_utc)):
        raise DomainError("INCOMPLETE_TIMELINE", 409)
    metric = metrics(frame)
    checks = constraint_checks(metric, request, frame)
    nominal = decision(checks.values()) if checks else None
    final = nominal if nominal is None or validation.get("passed") is True else "INDETERMINATE"
    soft, soft_violations = assess_soft(metric, request.constraints)
    result = {"metrics_hours": metric, "constraint_checks": checks,
        "nominal_sampled_decision": nominal, "decision": final,
        "soft_constraint_checks": soft, "soft_violations": soft_violations,
        "requirement_policy": "availability-and-contact-windows-v1" if request.contact_requirements else "availability-fractions-v1",
        "validation": validation}
    if request.contact_requirements is not None:
        result["contact_analysis"] = analyze_contacts({"request": request.model_dump(),
            "end_utc": request.end_utc, "timeline": records(frame[["start_utc", "end_utc", "earth_state"]]),
            "decision": final, "validation": validation}, **request.contact_requirements.model_dump())
    return result


