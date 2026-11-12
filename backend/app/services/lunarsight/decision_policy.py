"""Shared decision gate for mission and contact requirements."""


def decision_validated(validation):
    if not isinstance(validation, dict):
        return False
    path = validation.get("mission_path")
    return validation.get("passed") is True or (isinstance(path, dict) and path.get("passed") is True and
        path.get("scope") == "requested_sampled_sun_and_earth_paths_only")


def gated_decision(nominal, validation):
    # A hard rejection remains actionable even if evidence has quality warnings.
    # PASS still requires validation; unknown bounds are never a hard rejection.
    return nominal if nominal in (None, "FAIL") or decision_validated(validation) else "INDETERMINATE"
