"""Geometric visible solar-disc area, including solid-Earth occultation.

Midpoint vertical strips integrate area on the local angular sky plane. Missing
terrain never becomes sunlight: each strip contributes lower/upper area bounds.
The model excludes atmospheric eclipse dimming, limb darkening and power output.
"""
import numpy as np

VERSION = "solar-disc-mean-1.0"
SUN_RADIUS_KM = 695700.
EARTH_RADIUS_KM = 6378.137
STRIPS = 64


def fractions(sun, earth, profile, strips=STRIPS):
    from .visibility import lookup
    n = len(sun)
    lower, upper = np.zeros(n), np.ones(n)
    def column(frame, key):
        return frame[key].to_numpy(dtype=float) if key in frame else np.full(n, np.nan)
    az, el, distance = (column(sun, k) for k in ("az_deg", "el_deg", "distance_km"))
    eaz, eel, edistance = (column(earth, k) for k in ("az_deg", "el_deg", "distance_km"))
    valid_sun = (sun.row_present.eq(True).to_numpy() & np.isfinite(az+el+distance) & (distance > SUN_RADIUS_KM))
    valid_earth = (earth.row_present.eq(True).to_numpy() & np.isfinite(eaz+eel+edistance) & (edistance > EARTH_RADIUS_KM))
    chosen = np.flatnonzero(valid_sun)
    if not len(chosen):
        return lower, upper
    a, e = az[chosen], el[chosen]
    radius = np.rad2deg(np.arcsin(SUN_RADIUS_KM/distance[chosen]))
    cos_el = np.maximum(np.cos(np.deg2rad(e)), 1e-8)
    ex = ((eaz[chosen]-a+180) % 360-180)*cos_el
    ey = eel[chosen]-e
    er = np.rad2deg(np.arcsin(np.minimum(1., EARTH_RADIUS_KM/edistance[chosen])))
    earth_ok = valid_earth[chosen]
    eclipse = earth_ok & (np.hypot(ex, ey) < radius+er)

    # Most samples are fully lit or fully dark. A neighbourhood enclosing the
    # entire disk (and interpolation bins) makes these exits conservative.
    step = float(profile.az_step_deg.iloc[0])
    count = len(profile)
    bins = np.floor((a % 360)/step).astype(int)
    width = int(np.ceil(float(np.max(radius/cos_el))/step))+1
    # At zenith a disk spans all bearings. Never loop millions of redundant bins.
    offsets = range(-min(width, count), min(width, count)+1)
    h = profile.horizon_deg.to_numpy(dtype=float)
    coverage = profile.coverage_complete.to_numpy(dtype=bool)
    hmin, hmax = np.full(len(chosen), np.inf), np.full(len(chosen), -np.inf)
    complete = np.ones(len(chosen), dtype=bool)
    for offset in offsets:
        k = (bins+offset) % count
        complete &= coverage[k] & np.isfinite(h[k])
        hmin = np.minimum(hmin, h[k])
        hmax = np.maximum(hmax, h[k])
    lit = complete & earth_ok & ~eclipse & (e-radius >= hmax)
    dark = complete & (e+radius <= hmin)
    lower[chosen[lit]], upper[chosen[lit]] = 1., 1.
    lower[chosen[dark]], upper[chosen[dark]] = 0., 0.
    active = ~(lit | dark)
    if not active.any():
        return lower, upper
    indices = chosen[active]
    a, e, radius, cos_el, ex, ey, er = [v[active] for v in (a, e, radius, cos_el, ex, ey, er)]
    earth_ok, eclipse = earth_ok[active], eclipse[active]
    lo, hi, total = np.zeros(len(indices)), np.zeros(len(indices)), np.zeros(len(indices))
    for i in range(strips):
        unit_x = 2*(i+.5)/strips-1
        x = unit_x*radius
        half = np.sqrt(1-unit_x*unit_x)*radius
        bottom, top = e-half, e+half
        horizon, covered = lookup(profile, a+x/cos_el)
        finite = np.isfinite(horizon)
        # An incomplete but finite ray is a lower bound on obstruction only.
        floor = np.maximum(bottom, np.where(finite, horizon, bottom))
        visible = np.maximum(0., top-floor)
        maximum = visible.copy()
        minimum = np.where(covered & finite, visible, 0.)
        dx = x-ex
        intersects = eclipse & (np.abs(dx) < er)
        half_earth = np.sqrt(np.maximum(0., er*er-dx*dx))
        overlap = np.where(intersects, np.maximum(0., np.minimum(top, e+ey+half_earth)-np.maximum(floor, e+ey-half_earth)), 0.)
        maximum = np.maximum(0., maximum-overlap)
        minimum = np.maximum(0., minimum-overlap)
        lo += np.where(earth_ok, minimum, 0.)
        hi += maximum
        total += 2*half
    lower[indices] = np.clip(lo/total, 0., 1.)
    upper[indices] = np.maximum(lower[indices], np.clip(hi/total, 0., 1.))
    return lower, upper
