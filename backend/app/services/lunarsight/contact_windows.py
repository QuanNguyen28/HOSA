"""Earth-centre contact windows derived from full sampled timelines; standard library only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

METHOD_VERSION = "earth-contact-postprocess-1.0"
STATES = {"V", "B", "?"}


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamps must be ISO-8601 strings with a timezone")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Timestamps must include a timezone")
    return stamp.astimezone(timezone.utc)


def iso(stamp):
    return stamp.isoformat().replace("+00:00", "Z")


def minutes(start, end):
    return (end - start).total_seconds() / 60


def number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'} and finite")
    return float(value)


def runs(intervals, accepted):
    result = []
    for start, end, state in intervals:
        if state not in accepted:
            continue
        if result and result[-1][1] == start:
            result[-1] = (result[-1][0], end)
        else:
            result.append((start, end))
    return result


def longest(intervals, accepted):
    return max((minutes(a, b) for a, b in runs(intervals, accepted)), default=0.)


def minimum_check(lower, upper, limit):
    return "PASS" if lower >= limit else "FAIL" if upper < limit else "INDETERMINATE"


def aggregate(checks):
    if not checks:
        return None
    return "FAIL" if "FAIL" in checks else "INDETERMINATE" if "INDETERMINATE" in checks else "PASS"


def normalize(payload, start_utc=None, end_utc=None):
    if not isinstance(payload, dict):
        raise ValueError("Expected a backend result object or an object containing timeline")
    if "sample_stride" in payload or "points" in payload:
        raise ValueError("Display-sampled timelines are unsupported; use the full point-analysis result or native interval CSV")
    rows = payload.get("timeline")
    if not isinstance(rows, list) or not rows:
        raise ValueError("A nonempty full timeline is required; compare/search summaries and sparse blocking events are insufficient")
    parsed = []
    for row in rows:
        if not isinstance(row, dict) or row.get("earth_state") not in STATES:
            raise ValueError("Each interval must have earth_state V, B, or ?")
        a, b = timestamp(row.get("start_utc")), timestamp(row.get("end_utc"))
        if a >= b or (parsed and a < parsed[-1][1]):
            raise ValueError("Intervals must be positive, ordered and non-overlapping")
        parsed.append((a, b, row["earth_state"]))
    request = payload.get("request") or {}
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    declared_start = request.get("start_utc") or payload.get("start_utc")
    declared_end = payload.get("end_utc")
    if declared_end is None and declared_start and request.get("duration_hours") is not None:
        duration = number(request["duration_hours"], "duration_hours", positive=True)
        declared_end = iso(timestamp(declared_start) + timedelta(hours=duration))
    domain_start = timestamp(declared_start) if declared_start else parsed[0][0]
    domain_end = timestamp(declared_end) if declared_end else parsed[-1][1]
    start = timestamp(start_utc) if start_utc else domain_start
    end = timestamp(end_utc) if end_utc else domain_end
    if not domain_start <= start < end <= domain_end:
        raise ValueError("Analysis window must be positive and within the source result domain")
    intervals = []
    cursor = start
    for a, b, state in parsed:
        a, b = max(a, start), min(b, end)
        if a >= b:
            continue
        if cursor < a:
            intervals.append((cursor, a, "?"))
        intervals.append((a, b, state))
        cursor = b
    if cursor < end:
        intervals.append((cursor, end, "?"))
    return intervals, start, end, max(minutes(a, b) for a, b, _ in parsed)


def analyze_contacts(payload, *, start_utc=None, end_utc=None, min_contact_minutes=None,
                     setup_minutes=0, required_windows=None, first_contact_deadline_minutes=None,
                     max_gap_minutes=None):
    """Compute geometry-only windows and separately gated mission requirements.

    Duration bounds vary only missing evidence in this sampled model. Unknown
    intervals are never joined into a confirmed visible window. Window-count
    checks with unknown data remain indeterminate because filling an unknown
    interval can either create a new window or merge two existing windows.
    """
    setup = number(setup_minutes, "setup_minutes")
    minimum = None if min_contact_minutes is None else number(min_contact_minutes, "min_contact_minutes", positive=True)
    deadline = None if first_contact_deadline_minutes is None else number(first_contact_deadline_minutes, "first_contact_deadline_minutes")
    gap_limit = None if max_gap_minutes is None else number(max_gap_minutes, "max_gap_minutes")
    if required_windows is not None:
        if isinstance(required_windows, bool) or not isinstance(required_windows, int) or required_windows < 1:
            raise ValueError("required_windows must be a positive integer")
    if minimum is None and (required_windows is not None or deadline is not None or setup):
        raise ValueError("min_contact_minutes is required with setup, window count or first-contact deadline")
    intervals, start, end, step = normalize(payload, start_utc, end_utc)
    duration = minutes(start, end)
    if deadline is not None and deadline > duration:
        raise ValueError("First-contact deadline must be within the analysis window")
    unknown = sum(minutes(a, b) for a, b, s in intervals if s == "?")
    total = [sum(minutes(a, b) for a, b, s in intervals if s == "V"),
             sum(minutes(a, b) for a, b, s in intervals if s != "B")]
    contact = [longest(intervals, {"V"}), longest(intervals, {"V", "?"})]
    gap = [longest(intervals, {"B"}), longest(intervals, {"B", "?"})]
    windows = []
    threshold = None if minimum is None else minimum + setup
    for a, b in runs(intervals, {"V"}):
        length = minutes(a, b)
        windows.append({"start_utc": iso(a), "end_utc": iso(b), "duration_minutes": length,
                        "usable_duration_minutes": max(0., length - setup),
                        "qualifies": None if threshold is None else length >= threshold,
                        "touches_window_start": a == start, "touches_window_end": b == end,
                        "outside_window_duration_known": False})
    possible = runs(intervals, {"V", "?"})
    count = None if minimum is None else sum(w["qualifies"] for w in windows)
    checks = {}
    if threshold is not None:
        checks["min_contact_minutes"] = minimum_check(*contact, threshold)
    if required_windows is not None:
        checks["required_windows"] = ("INDETERMINATE" if unknown else
                                      "PASS" if count >= required_windows else "FAIL")
    if deadline is not None:
        stop = start + timedelta(minutes=deadline)
        prefix = [(a, min(b, stop), s) for a, b, s in intervals if a < stop]
        checks["first_contact_deadline_minutes"] = minimum_check(
            longest(prefix, {"V"}), longest(prefix, {"V", "?"}), threshold)
    if gap_limit is not None:
        checks["max_gap_minutes"] = ("PASS" if gap[1] <= gap_limit else
                                     "FAIL" if gap[0] > gap_limit else "INDETERMINATE")
    validation = payload.get("validation")
    validated = validation.get("passed") if isinstance(validation, dict) else None
    if validated is not None and not isinstance(validated, bool):
        raise ValueError("validation.passed must be a boolean")
    nominal = aggregate(checks.values())
    return {
        "schema_version": "1.0", "method_version": METHOD_VERSION,
        "scope": "sampled_earth_centre_visibility_within_analysis_window",
        "start_utc": iso(start), "end_utc": iso(end),
        "source": {"result_id": payload.get("result_id"), "method_version": payload.get("method_version"),
                   "dataset_version": payload.get("dataset_version"), "decision": payload.get("decision"),
                   "coordinate": payload.get("coordinate"), "request": payload.get("request"),
                   "validation_passed": validated, "validation": validation,
                   "coverage": payload.get("coverage"), "warnings": payload.get("warnings", [])},
        "sampling": {"max_source_interval_minutes": step,
                     "unknown_minutes_including_gaps": unknown,
                     "missing_evidence_bounds_only": True},
        "visible_windows": windows,
        "unknown_intervals": [{"start_utc": iso(a), "end_utc": iso(b), "duration_minutes": minutes(a, b)}
                              for a, b in runs(intervals, {"?"})],
        "metrics": {"total_los_minutes_bounds": total, "longest_contact_minutes_bounds": contact,
                    "max_gap_minutes_bounds": gap, "visible_windows_count": len(windows),
                    "qualified_windows_count": count,
                    "qualified_windows_count_complete": unknown == 0,
                    "qualified_visible_minutes": None if minimum is None else
                        sum(w["usable_duration_minutes"] for w in windows if w["qualifies"]),
                    "first_contact_wait_minutes": {
                        "earliest_possible": minutes(start, possible[0][0]) if possible else None,
                        "first_confirmed": minutes(start, timestamp(windows[0]["start_utc"])) if windows else None}},
        "requirements": {"min_contact_minutes": minimum, "setup_minutes": setup,
                         "required_windows": required_windows,
                         "first_contact_deadline_minutes": deadline, "max_gap_minutes": gap_limit,
                         "sampled_checks": checks, "nominal_sampled_decision": nominal,
                         "decision": nominal if validated is True or nominal is None else "INDETERMINATE"},
        "limitations": [
            "Geometric visibility of the Earth centre; no ground-station schedule or RF link budget.",
            "Half-open sampled intervals; bounds do not include unsampled events or DEM uncertainty.",
            "Initial and final no-contact periods count toward max_gap; windows are clipped to the analysis domain.",
            "A deadline requires setup plus the requested continuous contact to FINISH before that deadline.",
            "Source validation is retained; missing or failed validation gates requirement decisions to INDETERMINATE.",
        ],
    }

