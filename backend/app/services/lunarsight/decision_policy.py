"""Shared decision gate for mission and contact requirements."""


def decision_validated(validation):
    if not isinstance(validation, dict):
        return False
    path = validation.get("mission_path")
    return validation.get("passed") is True or (isinstance(path, dict) and path.get("passed") is True and
        path.get("scope") == "requested_sampled_sun_and_earth_paths_only")


def gated_decision(nominal, validation, *, checks=None):
    temporal = (validation.get("sensitivity", {}).get("time_5min_vs_1min", {}).get("constraint_checks")
                if isinstance(validation, dict) else None)
    if nominal == "FAIL" and checks and temporal is not None:
        # Do not turn a coarse-grid failure contradicted by the fine grid into
        # a final rejection. At least one SAME hard requirement must fail both.
        if not any(state == "FAIL" and temporal.get(name) == "FAIL" for name, state in checks.items()):
            return "INDETERMINATE"
    # A hard rejection remains actionable even if evidence has quality warnings.
    # PASS still requires validation; unknown bounds are never a hard rejection.
    return nominal if nominal in (None, "FAIL") or decision_validated(validation) else "INDETERMINATE"
