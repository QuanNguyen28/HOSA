"""Hard availability requirements and independent soft continuity preferences."""
import math

from app.core.errors import DomainError
from .models import Constraints

METRICS = ("total_sun_hours", "total_earth_los_hours", "longest_dark_hours", "longest_blackout_hours", "longest_joint_hours")
LIMIT_METRICS = {"max_darkness_hours": "longest_dark_hours", "max_earth_blackout_hours": "longest_blackout_hours"}
MINIMUM_METRICS = {"min_sunlit_fraction": "total_sun_hours", "min_earth_los_fraction": "total_earth_los_hours"}


def validate_metrics(metrics: dict, duration: float = 72) -> None:
    if set(metrics) != set(METRICS):
        raise DomainError("ENGINE_CONTRACT_ERROR", 502)
    for pair in metrics.values():
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise DomainError("ENGINE_CONTRACT_ERROR", 502)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
               or v < -1e-7 or v > duration+1e-7 for v in pair) or pair[0] > pair[1]:
            raise DomainError("ENGINE_CONTRACT_ERROR", 502)


def decision(checks):
    return "FAIL" if "FAIL" in checks.values() else "PASS" if all(
        v == "PASS" for v in checks.values()) else "INDETERMINATE"


def hard_checks(metrics, min_sunlit_fraction, min_earth_los_fraction, duration=72):
    checks = {}
    for name, limit in (("min_sunlit_fraction", min_sunlit_fraction), ("min_earth_los_fraction", min_earth_los_fraction)):
        if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or not 0 <= limit <= 1:
            raise ValueError(f"{name} must be a finite fraction in [0,1]")
        low, high = [v/duration for v in metrics[MINIMUM_METRICS[name]]]
        checks[name] = "PASS" if low >= limit-1e-9 else "FAIL" if high < limit-1e-9 else "INDETERMINATE"
    return checks


def assess(metrics: dict, constraints: Constraints, min_sunlit_fraction, min_earth_los_fraction, duration=72):
    validate_metrics(metrics, duration)
    checks = hard_checks(metrics, min_sunlit_fraction, min_earth_los_fraction, duration)
    violations = []
    for name, limit in (("min_sunlit_fraction", min_sunlit_fraction), ("min_earth_los_fraction", min_earth_los_fraction)):
        if checks[name] == "FAIL":
            low, high = [v/duration for v in metrics[MINIMUM_METRICS[name]]]
            violations.append({"constraint": name, "limit": limit, "unit": "fraction",
                "shortfall_bounds": [max(0., limit-high), max(0., limit-low)]})
    return decision(checks), checks, violations


def assess_soft(metrics, constraints):
    checks, violations = {}, []
    for name, metric in LIMIT_METRICS.items():
        limit = getattr(constraints, name)
        if limit is None:
            continue
        low, high = metrics[metric]
        checks[name] = "PASS" if high <= limit+1e-9 else "FAIL" if low > limit+1e-9 else "INDETERMINATE"
        if checks[name] == "FAIL":
            violations.append({"constraint": name, "limit": limit, "unit": "hours",
                "excess_bounds": [max(0., low-limit), max(0., high-limit)]})
    return checks, violations


def soft_preference_key(candidate):
    """Only break primary-metric ties; no weighted quality score."""
    states = candidate.soft_constraint_states.values()
    return sum(v == "FAIL" for v in states), sum(v == "INDETERMINATE" for v in states)


def violation_key(candidate, constraints, min_sunlit_fraction, min_earth_los_fraction, duration=72):
    """Near misses are ordered by their largest relative hard shortfall only."""
    deficits = [max(0., limit-candidate.metrics[metric][0]/duration)/max(limit, 1e-9)
        for limit, metric in ((min_sunlit_fraction, "total_sun_hours"), (min_earth_los_fraction, "total_earth_los_hours"))
        if limit is not None]
    # Contact failures are explicit near misses, never feasible recommendations.
    contact_failures = sum(key.startswith("contact.") and state == "FAIL"
                           for key, state in candidate.constraint_states.items())
    return max(deficits, default=0.), contact_failures
