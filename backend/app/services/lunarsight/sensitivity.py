"""Reassess numerical sensitivity for the exact request, using local evidence only.

The 1-minute queries cover a declared test window, not the entire scenario.
Missing comparison coverage must never inherit a stable label from another date.
"""
import csv
import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from .durations import bounds, combine


def _utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


@lru_cache(maxsize=32)
def _read(path, mtime_ns, size):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return tuple(csv.DictReader(stream))


def _rows(path):
    stat = path.stat()
    return _read(str(path), stat.st_mtime_ns, stat.st_size)


def _ephemeris(root, site_id, body, start, end, minutes):
    expected = int((end-start).total_seconds() / (minutes*60)) + 1
    for path in sorted((root/"ephemeris").glob(f"{site_id}_{body}_{minutes}min_*.csv")):
        rows = [r for r in _rows(path) if start <= _utc(r["utc"]) <= end]
        if len(rows) != expected:
            continue
        if any(_utc(r["utc"]) != start+timedelta(minutes=k*minutes) for k, r in enumerate(rows)):
            continue
        if any(r["row_present"].lower() != "true" or not all(
                r[key] and math.isfinite(float(r[key])) for key in ("az_deg", "el_deg")) for r in rows):
            continue
        return rows, path
    return None


def _horizon(profile, azimuth):
    step = float(profile[0]["az_step_deg"])
    n = len(profile)
    if not math.isclose(n*step, 360) or any(
            not math.isclose(float(r["az_deg"]), k*step, abs_tol=1e-9) for k, r in enumerate(profile)):
        raise ValueError("Invalid comparison horizon grid")
    result = []
    for az in azimuth:
        x = (az % 360)/step
        i = int(x) % n
        j = (i+1) % n
        fraction = x-math.floor(x)
        exact = math.isclose(fraction, 0, abs_tol=1e-10)
        covered = profile[i]["coverage_complete"].lower() == "true" and (
            exact or profile[j]["coverage_complete"].lower() == "true")
        hi, hj = float(profile[i]["horizon_deg"] or "nan"), float(profile[j]["horizon_deg"] or "nan")
        horizon = hi if exact else hi*(1-fraction)+hj*fraction if covered else math.nan
        result.append((horizon, covered))
    return result


def _series(root, prefix, ephemerides, step):
    states = []
    sources = []
    for body, height in (("sun", 1), ("earth", 2)):
        rows, path = ephemerides[body]
        profile_path = root/"horizon"/f"{prefix}_h{height}_az{step}_r400000.csv"
        profile = _rows(profile_path)
        horizons = _horizon(profile, [float(r["az_deg"]) for r in rows[:-1]])
        state = []
        for row, (h, covered) in zip(rows[:-1], horizons):
            el = float(row["el_deg"])
            state.append("?" if not math.isfinite(h) else "B" if el <= h else "V" if covered else "?")
        states.append(state)
        sources.extend([str(path), str(profile_path)])
    times = [_utc(r["utc"]) for r in ephemerides["sun"][0]]
    weights = [(b-a).total_seconds()/3600 for a, b in zip(times, times[1:])]
    return bounds(*states, weights), (times[:-1], states), sources


def _event_shift(base, other):
    """Pair like transitions once; expose unmatched events rather than hiding them."""
    def events(series):
        times, states = series
        output = []
        for body, values in enumerate([*states, combine(*states).tolist()]):
            output.extend((times[k], body, values[k-1], values[k]) for k in range(1, len(values))
                          if values[k] != values[k-1])
        return output
    first, second = events(base), events(other)
    remaining = set(range(len(second)))
    shifts = []
    for at, *transition in first:
        choices = [(abs((second[k][0]-at).total_seconds())/60, k) for k in remaining
                   if list(second[k][1:]) == transition]
        if choices:
            shift, index = min(choices)
            if shift <= 15:
                remaining.remove(index)
                shifts.append(shift)
    return max(shifts, default=None), len(first)+len(second)-2*len(shifts)


def summarize(root, site_id, prefix, start, end, baseline_metrics, evaluate, scope, geometry, soft_evaluate=lambda _: {}):
    """evaluate(metrics) returns constraint states for the user's current inputs."""
    baseline_checks = evaluate(baseline_metrics)
    def decision(checks):
        return "FAIL" if "FAIL" in checks.values() else "PASS" if all(
            v == "PASS" for v in checks.values()) else "INDETERMINATE"
    baseline_soft = soft_evaluate(baseline_metrics)
    baseline = dict(metrics=baseline_metrics, constraint_states=baseline_checks, decision=decision(baseline_checks),
                    soft_constraint_states=baseline_soft)
    comparisons = {}
    sources = set()
    series = {}
    max_angle = None
    try:
        differences = []
        for height in (1, 2):
            base_path = root/"horizon"/f"{prefix}_h{height}_az0.25_r400000.csv"
            fine_path = root/"horizon"/f"{prefix}_h{height}_az0.125_r400000.csv"
            fine = _rows(fine_path)
            interpolated = _horizon(_rows(base_path), [float(r["az_deg"]) for r in fine])
            differences.extend(abs(h-float(r["horizon_deg"])) for r, (h, _) in zip(fine, interpolated)
                               if r["horizon_deg"] and math.isfinite(h) and math.isfinite(float(r["horizon_deg"])))
            sources.update([str(base_path), str(fine_path)])
        max_angle = max(differences, default=None)
    except FileNotFoundError:
        pass
    for minutes, az_step, name in ((5, "0.125", "azimuth_0.25_vs_0.125"), (1, "0.25", "time_5min_vs_1min")):
        ephemerides = {body: _ephemeris(root, site_id, body, start, end, minutes) for body in ("sun", "earth")}
        try:
            if any(value is None for value in ephemerides.values()):
                comparisons[name] = {"status": "NOT_EVALUATED", "reason": "COMPARISON_WINDOW_NOT_COVERED"}
                continue
            metrics, series[name], paths = _series(root, prefix, ephemerides, az_step)
            sources.update(paths)
        except FileNotFoundError:
            comparisons[name] = {"status": "NOT_EVALUATED", "reason": "COMPARISON_PROFILE_MISSING"}
            continue
        checks = evaluate(metrics)
        same = checks == baseline_checks
        comparison_status = "REVIEW" if not same else "NOT_EVALUATED" if "INDETERMINATE" in checks.values() else "STABLE_DECISION"
        comparisons[name] = dict(status=comparison_status,
            baseline=baseline, alternative=dict(metrics=metrics, constraint_states=checks, decision=decision(checks),
                soft_constraint_states=soft_evaluate(metrics)),
            soft_preferences_changed=soft_evaluate(metrics) != baseline_soft,
            bounds_abs_delta_minutes={key: [abs(a-b)*60 for a, b in zip(baseline_metrics[key], pair)]
                                      for key, pair in metrics.items()})
        if comparison_status == "NOT_EVALUATED":
            comparisons[name]["reason"] = "INDETERMINATE_CONSTRAINTS"
    statuses = [v["status"] for v in comparisons.values()]
    status = "REVIEW" if "REVIEW" in statuses else "NOT_EVALUATED" if "NOT_EVALUATED" in statuses else "STABLE_DECISION"
    # Temporal event shifts require both native grids and the baseline profile.
    temporal = comparisons["time_5min_vs_1min"]
    shift, unmatched = None, None
    if temporal["status"] != "NOT_EVALUATED":
        ephemerides = {body: _ephemeris(root, site_id, body, start, end, 5) for body in ("sun", "earth")}
        if all(value is not None for value in ephemerides.values()):
            _, base_series, paths = _series(root, prefix, ephemerides, "0.25")
            sources.update(paths)
            shift, unmatched = _event_shift(base_series, series["time_5min_vs_1min"])
    duration_delta = max((v for pair in temporal.get("bounds_abs_delta_minutes", {}).values() for v in pair), default=None)
    repo = root.parents[3]
    return dict(status=status, scope=scope, comparisons=comparisons,
        soft_preferences_changed=any(v.get("soft_preferences_changed", False) for v in comparisons.values()),
        angular_sensitive=None if max_angle is None else max_angle > geometry["tol_horizon_deg"],
        max_horizon_difference_deg=max_angle, angular_difference_scope="full_azimuth_profile",
        time_sensitive=None if duration_delta is None else bool(
            temporal["status"] == "REVIEW" or duration_delta > geometry["tol_duration_minutes"]
            or (shift or 0) > geometry["tol_event_minutes"] or unmatched),
        max_duration_difference_minutes=duration_delta, max_event_shift_minutes=shift,
        unmatched_events=unmatched, sources=sorted(str(Path(p).relative_to(repo)) for p in sources),
        source="request-time comparison of local ephemerides and horizon profiles")
