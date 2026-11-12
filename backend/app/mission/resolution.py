"""Bounded numerical revalidation, independent of mission feasibility thresholds."""
from copy import deepcopy

VERSION = "indeterminate-resolution-2.1"
FINE_AZIMUTH_STEPS = (.0625, .03125)
# Corrupt inputs and failed geometry/seams must never be bypassed by this policy.
BLOCKING_REASONS = {"DEM_SEAM_FAILED", "ENU_REFERENCE_FAILED", "SNAPSHOT_INTEGRITY_FAILED",
                    "SITE01_GEOMETRY_GATE_FAILED"}
RECOVERABLE_CODES = {"COMPARISON_EVIDENCE_MISSING", "SENSITIVITY_FAILED", "INCOMPLETE_TERRAIN",
                     "INCOMPLETE_EPHEMERIS"}


def can_recompute(validation):
    reasons = validation.get("reason_codes", [])
    return bool(reasons) and not any(r in BLOCKING_REASONS for r in reasons) and all(
        reason.rsplit(":", 1)[-1] in RECOVERABLE_CODES for reason in reasons)


def can_refine(validation):
    """Angular refinement only addresses angular sensitivity, never missing DEM or ephemerides."""
    reasons = validation.get("reason_codes", [])
    return bool(reasons) and all(r.startswith("azimuth_") and r.endswith(":SENSITIVITY_FAILED") for r in reasons)


def attempt(evaluation, coarse_step, fine_step):
    return {"coarse_az_step_deg": coarse_step, "fine_az_step_deg": fine_step,
            "decision": evaluation["decision"], "nominal_sampled_decision": evaluation["nominal_sampled_decision"],
            "validation_passed": evaluation["validation"]["passed"],
            "mission_path_passed": evaluation["validation"].get("mission_path", {}).get("passed", False),
            "reason_codes": list(evaluation["validation"]["reason_codes"]),
            "metrics_hours": deepcopy(evaluation["metrics_hours"])}


def snapshot_origin(result):
    return {"provider": "snapshot", "decision": result["decision"],
            "nominal_sampled_decision": result["nominal_sampled_decision"],
            "reason_codes": list(result["validation"].get("reason_codes", [])),
            "provenance": deepcopy(result["provenance"])}
