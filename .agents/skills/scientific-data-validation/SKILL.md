---
name: scientific-data-validation
description: Validate LunarSight ENU horizons, three-state visibility, duration bounds and numerical sensitivity. Use before exporting derived lunar terrain results.
---

# scientific-data-validation

Inputs: checked NASA DEM/ROI, Horizons observer/UTC, geometry and scenario configs. Outputs: test logs, coverage, numerical differences and a gated result. Use NumPy, Pandas and pytest; follow the project proposal's data/science acceptance cases.

1. Test four geographic directions, an analytic obstacle and the exact curvature of a uniform sphere. Verify real blocker elevations independently in Cartesian ENU. Compare overlapping DEM profiles around each seam; document differences and avoid an unverified datum adjustment.
2. Use B for equality or a known blocker, V for strictly above a valid horizon with required coverage, and ? for missing evidence. Exercise all nine AND combinations and half-open intervals, irregular weights, missing rows, threshold equality and the last supported start.
3. Compare 0.25/0.125-degree rays, at least two scan radii and independently fetched 5/1-minute ephemerides on a declared window. Log angular differences, coverage, shifted or unmatched events, duration bounds and changed decisions. Treat unapproved tolerances as provisional.
4. Gate Site04 on Site01; fail closed for incompatible geometry. Archive exact inputs, test logs and the result's limitations. Synthetic fixtures may never appear as real input data.

References: [LOLA 5 m methodology](https://ntrs.nasa.gov/citations/20205009660), [regional LOLA methodology](https://doi.org/10.3847/PSJ/acf3e1), [Horizons azimuth/elevation](https://ssd.jpl.nasa.gov/horizons/manual.html). Project workflow: `src/horizon.py`, `src/visibility.py`, `tests/`.
