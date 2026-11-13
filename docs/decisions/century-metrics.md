# Prepared catalog metrics, 2000–2100

The prepared band is `[2000-01-01T00:00:00Z, 2101-01-01T00:00:00Z)`: it includes every calendar year from 2000 through 2100. The current catalog has 27 named NASA entries at 26 distinct coordinates, prepared at equal panel/antenna heights of 2, 10, 20 and 30 m (104 physical configurations). See [NASA catalog](nasa-default-catalog.md). This is prepared-data coverage, not an API mission-duration limit. Other coordinates, heights and unprepared endpoint times still use Analyze.

`POST /api/lunar/point/metrics` returns nominal metrics and all three Sun/Earth/Joint preview charts together. Requirements and validation remain `not_started`, and `decision` remains null. A century of displayed metrics does not approve a century-long mission.

## Construction and deployment

```bash
make metrics-century-prepare
```

This builds resumable, independently checked calendar-year parts using the existing five-minute visibility calculation, solar-disc fractions, terrain profiles and verified shared SPICE ephemeris. Each part retains source identity, native frame hash, ephemeris interpolation checks and index checksum. Daily segment-tree leaves preserve duration bounds and longest runs across year boundaries. Hourly weighted sums support at most 800 chart bins. Native frames are discarded after indexing; no century-sized native timeline needs to be retained.

An aggregate is published atomically only after all contiguous parts are available. Short queries use a verified yearly part when possible. Longer queries use the combined index. Neither path recomputes visibility or queues analysis. Changed coordinates, heights, profiles, algorithm versions or kernel hashes cannot reuse an incompatible index. Corrupt products fail closed; unsupported coverage is never clamped.

Deploy `data/cache/point-analysis/prepared-metrics/` alongside the verified kernels and prepared terrain package on persistent storage. This directory is ignored by Git; pushing source code alone does not ship prepared data. The `.parts/` subdirectories improve short-range loading and permit resumable builds; the combined published products can serve metrics without them. Detailed native intervals and scientific validation are still calculated on demand.

## Evidence

- [Kernel coverage](../validation/lunarsight/century-kernel-coverage.json): actual installed DE440s and lunar orientation coverage encloses the requested band; 1,213 exact monthly boundary probes succeeded.
- [JPL comparisons](../validation/lunarsight/century-jpl-validation.json): eight Sun/Earth comparisons for Site01 and Site04 at the beginning of 2000 and end of 2100, using official one-minute Horizons samples.
- [Build report](../validation/lunarsight/century-metrics-build.json): per-coordinate source identities, checksums, interval counts and preparation times.
- [HTTP and native-window verification](../validation/lunarsight/century-metrics-http.json): full-band responses, chart integrals, independent native scans at both ends and across a year boundary, leap-year cases and rejected out-of-band requests.

Reproduce the HTTP/native checks against the running backend:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_long_range_metrics.py \
  --output docs/validation/lunarsight/century-metrics-http.json
```

These checks verify nominal computation and selected numerical comparisons. They do not establish continuous-time visibility bounds or complete scientific validation for every instant of the century. Chart bins are duration-weighted summaries, not instantaneous observations; uncertainty bounds remain visible.

## Historical result before the NASA catalog migration

The following 23-coordinate report is historical. Current reports use the `nasa27-` prefix in `docs/validation/lunarsight/`.

All 23 coordinates were prepared successfully: 101 yearly parts and 10,624,320 five-minute intervals per coordinate. Published combined indices total 293,577,534 bytes; the local directory, including yearly checkpoints, occupies about 585 MiB.

Real local HTTP responses for the full band, including metrics and 800 bins for each chart, took 23–185 ms per coordinate. All 69 independently recomputed native windows matched indexed metrics, with maximum absolute difference below 0.000000004 seconds. Chart integrals, cross-year runs, leap-year 2000, non-leap-year 2100 and rejected out-of-band requests passed; no analysis jobs were created. The eight selected JPL comparisons had maximum angular error below 0.000075°.

Regression: 423 backend tests passed, one skipped; 47 frontend tests passed; production build succeeded. Browser acceptance displayed Site04 for the entire band with METRICS READY and all three charts without submitting Analyze.
