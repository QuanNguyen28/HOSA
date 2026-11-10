"""Duration bounds shared by the scientific pipeline and request-time checks."""
import numpy as np


def combine(s, e):
    s, e = np.broadcast_arrays(s, e)
    if not (np.isin(s, ["V", "B", "?"]).all() and np.isin(e, ["V", "B", "?"]).all()):
        raise ValueError("Unknown state code")
    return np.where((s == "B") | (e == "B"), "B", np.where((s == "V") & (e == "V"), "V", "?"))


def longest(ok, dt):
    ok = np.asarray(ok, dtype=bool)
    edges = np.flatnonzero(np.diff(np.r_[False, ok, False]))
    if not len(edges):
        return 0.
    ends = np.r_[0., np.cumsum(dt)]
    return float(np.max(ends[edges[1::2]] - ends[edges[::2]]))


def bounds(sun, earth, dt):
    s, e, dt = np.asarray(sun), np.asarray(earth), np.asarray(dt, dtype=float)
    if s.ndim != 1 or e.shape != s.shape or dt.shape != s.shape or not np.isfinite(dt).all() or (dt <= 0).any():
        raise ValueError("Invalid intervals")
    j = combine(s, e)
    return dict(total_sun_hours=[float(dt[s == "V"].sum()), float(dt[s != "B"].sum())],
        total_earth_los_hours=[float(dt[e == "V"].sum()), float(dt[e != "B"].sum())],
        longest_dark_hours=[longest(s == "B", dt), longest(s != "V", dt)],
        longest_blackout_hours=[longest(e == "B", dt), longest(e != "V", dt)],
        longest_joint_hours=[longest(j == "V", dt), longest(j != "B", dt)])
