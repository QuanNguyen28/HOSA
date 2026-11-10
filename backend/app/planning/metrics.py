"""Pure interval decisions: unknown values never become zeros."""
import math

from app.core.errors import DomainError
from .models import Constraints

METRICS = ("total_sun_hours", "longest_dark_hours", "longest_blackout_hours", "longest_joint_hours")
LIMIT_METRICS = {"max_darkness_hours": "longest_dark_hours", "max_earth_blackout_hours": "longest_blackout_hours"}


def validate_metrics(metrics: dict, duration: float = 72) -> None:
    if set(metrics) != set(METRICS):
        raise DomainError("ENGINE_CONTRACT_ERROR", 502)
    for pair in metrics.values():
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise DomainError("ENGINE_CONTRACT_ERROR", 502)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
               or v < -1e-7 or v > duration+1e-7 for v in pair) or pair[0] > pair[1]:
            raise DomainError("ENGINE_CONTRACT_ERROR", 502)


def assess(metrics: dict, constraints: Constraints, min_sunlit_fraction=None, duration=72) -> tuple[str, dict, list]:
    validate_metrics(metrics, duration)
    checks, violations = {}, []
    for name, metric in LIMIT_METRICS.items():
        low, high = metrics[metric]
        limit = getattr(constraints, name)
        state = "PASS" if high <= limit+1e-9 else "FAIL" if low > limit+1e-9 else "INDETERMINATE"
        checks[name] = state
        if state == "FAIL":
            violations.append({"constraint": name, "limit": limit, "unit": "hours",
                               "excess_bounds": [max(0, low-limit), max(0, high-limit)]})
    if min_sunlit_fraction is not None:
        low, high = [v/duration for v in metrics["total_sun_hours"]]
        state = "PASS" if low >= min_sunlit_fraction-1e-9 else "FAIL" if high < min_sunlit_fraction-1e-9 else "INDETERMINATE"
        checks["min_sunlit_fraction"] = state
        if state == "FAIL":
            violations.append({"constraint": "min_sunlit_fraction", "limit": min_sunlit_fraction,
                               "unit": "fraction", "shortfall_bounds": [min_sunlit_fraction-high, min_sunlit_fraction-low]})
    decision = "FAIL" if "FAIL" in checks.values() else "PASS" if all(v == "PASS" for v in checks.values()) else "INDETERMINATE"
    return decision, checks, violations


def violation_key(candidate, constraints, min_sunlit_fraction=None, duration=72):
    """An explicit fallback policy; never presented as a scientific quality score."""
    ratios = [max(0, candidate.metrics[metric][1]-getattr(constraints, name))/max(getattr(constraints, name), 1e-9)
              for name, metric in LIMIT_METRICS.items()]
    if min_sunlit_fraction is not None:
        ratios.append(max(0, min_sunlit_fraction-candidate.metrics["total_sun_hours"][0]/duration)/max(min_sunlit_fraction, 1e-9))
    return max(ratios)
