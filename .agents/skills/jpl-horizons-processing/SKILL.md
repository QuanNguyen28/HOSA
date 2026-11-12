---
name: jpl-horizons-processing
description: Retrieve and validate Moon topocentric Sun and Earth angles from JPL Horizons. Use for lunar observers, ephemeris parsing, or coverage checks.
---

# jpl-horizons-processing

Inputs: verified lunar site and radial datum, target-specific device height, aligned UTC bounds. Outputs: raw responses, request identity/headers, parsed CSV and coverage summary. Use Requests, Pandas and NumPy.

1. Follow the [API](https://ssd-api.jpl.nasa.gov/doc/horizons.html) and [manual](https://ssd.jpl.nasa.gov/horizons/manual.html). Set coord@301, GEODETIC, QUANTITIES=4, AIRLESS; target 10 (Sun) at 1 m and 399 (Earth) at 2 m. Longitude is east-positive; altitude is km after conversion from the DEM radius to the independently checked reference shape.
2. Verify target, Moon centre, Mean Earth frame, three radii, geodetic echo, units, time scale and step in the result. DE441 in the ephemeris source does not identify the lunar observer frame.
3. Preserve raw payload and parameters under an exact cache key. Parse between the markers by column names. Reject duplicated/off-grid times and a missing terminal timestamp. Preserve missing angles and interior rows as missing; never fill with zero.
4. Require synchronized target grids and coverage through the request's actual end time; do not hard-code 72 hours when the active `MissionRequest` supports another duration. Make an actual independent one-minute query for a sensitivity case. No scientific PASS if frame or coverage is unverified. Existing P1 snapshots are point-specific and cannot stand in for a new coordinate observer.

Project workflow: `scripts/notebooks/03_horizons_eda.ipynb`, `backend/app/mission/`, `backend/app/point_analysis/`, and the existing versioned snapshot receipts. Keep fixed P1 scenario coverage separate from request-parameterized coordinate calculations. Check missing/duplicate-row fixtures, observer identity, and a real response for the exact requested observer.
