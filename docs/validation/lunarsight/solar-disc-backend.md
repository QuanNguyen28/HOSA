# Solar-disc backend acceptance — 2026-11-12

Branch: `feat/merge-fe-be`. No live LLM calls; local OpenRouter configuration is
preserved. Astronomy inputs are official NAIF/JPL kernels and previously
hash-verified JPL observer responses; terrain is the installed NASA DEM data.

## Automated checks

- Final integrated verification: 404 backend tests passed, 1 skipped (optional unavailable Site06 data).
- 40 frontend tests passed and production build/typecheck passed.
- Added analytic circular-segment, partial/total occultation, missing evidence,
  irregular duration weighting, azimuth wrap, monthly boundaries, calendar
  overflow, cache corruption, observer parallax, threshold/cache independence,
  route/CSV agreement and mission-path full/partial-disk regressions.
- Older snapshot regression fixtures explicitly request `sun_center`; new
  default-model tests assert `solar_disc`. Historical datasets were not edited.
- Chat adapter regression uses local fixture providers, not paid/live inference.

## Real-data and live API evidence

[Machine-readable report](solar-disc-backend.json), reproduced by:

```bash
PYTHONPATH=.:backend backend/.venv/bin/python scripts/verify_solar_disc_backend.py \
  --base-url http://127.0.0.1:8001 \
  --output docs/validation/lunarsight/solar-disc-backend.json
```

Eight comparisons cover Site01/Site04, Sun/Earth and independently archived
native JPL 1/5-minute grids, over 72 hours. Maximum azimuth difference is about
0.000104 degrees; maximum elevation difference about 0.000063 degrees, within
the declared 0.001-degree check. Exact SPICE interpolation probes are separate.

Two documented points outside Site01/Site04 still return PASS and FAIL. Their
live Point, Compare, one-start Search and CSV results agree, including the
underlying point result ID and declared illumination model. Point HTTP calls
were approximately 1 second with no completed-result cache; terrain was cached.
The 240-hour request returns PASS under conservative mission-path bounds while
retaining its failed full-horizon diagnostics.

Direct UI check: Site04, 20 m panel/antenna, 1–31 March 2026 selected by target
end date, reports 91.5658% mean disk visibility and PASS after two successful
angular refinements. At 3 March 09:50 UTC it shows 75.0% of the disk while the
centre is still visible. [Case metadata](solar-disc-ui-case.json) retains the
request, result ID, resolution attempts and example sample. First-time fine
terrain refinement in this case took several minutes; that cold spatial work
is outside the cached-horizon performance measurements below. The later
[catalog precompute package](../../decisions/catalog-precompute.md) now includes
these refinement profiles for the default observers/heights.

An occultation regression uses real SPICE on 3 March 2026 with an explicitly
declared flat skyline to isolate eclipse geometry; it does not claim to be a
terrain evaluation at that coordinate. It exercises full, partial and zero
solar visibility. Maximum difference between 64 and 2048 strips is 0.000444 of
disk area. The analytic half-disk regression independently gives 50% and FAIL
at an 80% requirement.

## Performance scope

Fresh completed-result caches were seeded only with existing verified terrain
profiles. Local hourly tables and kernel data are reusable. Representative
72-hour runs took about 0.7–1.0 seconds; 240 hours about 1.3 seconds in the final
report. Cache-hit reads are separately reported. These are not timings for a
new coordinate's first DEM scan, kernel download, browser rendering or network
transfer.

[Two-year measurement](solar-disc-long-performance.json): 17,520 hours,
210,240 output intervals, full 1/5-minute validation and JSON/CSV artifacts,
about 12.6 seconds with warmed terrain/hourly tables and an isolated result
cache. No profiler was enabled for that measurement. Metrics and decision match
the pre-serialization-optimization run. The full JSON is about 140 MB; large
response transfer/parsing still has a cost. The UI aggregates display bins
without changing backend samples or decisions.

That two-year case intentionally remains INDETERMINATE: nominal mean solar-disc
visibility is about 80.108%, close to the 80% requirement, and full numerical
validation does not pass. Runtime speed and the new disk metric do not justify
removing scientific uncertainty.

## Local setup and direct request

```bash
make backend-install
make ephemeris-prepare
```

Warm a chosen range if desired:

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/prepare_shared_ephemeris.py \
  --start 2026-11-01T00:00:00Z --end 2026-12-01T00:00:00Z
```

Request example:

```bash
curl http://127.0.0.1:8001/api/lunar/point/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/point-solar-disc-request.json
```

Read `illumination.mean_visible_fraction_bounds` for the mean disk fraction,
`metrics_hours.total_sun_hours` for equivalent full-disc hours, and timeline
`sun_visible_fraction` / lower / upper for individual sampled intervals. A null
nominal fraction denotes unresolved evidence; lower/upper bounds remain usable.
