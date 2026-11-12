# Metrics and preview charts before evaluation

Catalog browsing and changing dates now request `POST /api/lunar/point/metrics` automatically. It returns provisional Sun/Earth/Joint metrics and preview charts directly from a prepared index, independently of analysis worker queues. It never calculates ephemerides, scans a native timeline, writes a native preview, or schedules validation. The UI shows **METRICS READY**; **Analyze point** runs hard requirements and scientific validation separately.

The index uses the same verified nominal five-minute series and solar-disc model. Daily leaves retain weighted sunlight sums, Earth/Joint duration bounds, and prefix/suffix/maximum runs for both bounds of darkness, blackout and joint visibility. A segment tree combines ranges without visiting every native sample and preserves runs crossing midnight. Identity retains kernel/provider, exact coordinate, heights, terrain profiles and algorithm versions. Index bytes are SHA-256 checked and tied to the source artifact hash. Index values never approve a PASS.

Version 2 also stores hourly weighted sums. Queries turn these into at most 800 display bins, in the same response as metrics. Bar height shows mean Sun-disc fraction or visible Earth/Joint time; hatching means uncertain bounds. All preview rows are marked `aggregated`, with `exact_intervals_ready: false`, and are never used as exact instantaneous evidence. For uncached analyses, the client refreshes an initially empty preview until its chart arrives, before final evaluation finishes.

An unindexed range returns `409 METRICS_NOT_PREPARED`. Explicit Analyze remains available for new coordinates, heights or dates. This is cache coverage, not a mission-duration maximum. Endpoints outside indexed day/entry boundaries also use that workflow; they are never silently rounded or clamped.

Without an index, the analysis job publishes metrics JSON as soon as initial native metrics exist. Display aggregation, binary preview writes, physical-cache writes and index construction follow publication. Until exact interval evidence exists, its endpoint returns `409 POINT_INTERVAL_NOT_READY`; the browser never treats a missing/display timeline as an exact Sun/Earth state.

## Preparation and deployment

```bash
# Index existing nominal physical series:
make metrics-prepare

# Prepare a new physical band and its index:
PYTHONPATH=backend backend/.venv/bin/python scripts/prepare_physical_series.py \
  --sites Site04_P1 --start 2026-01-01T00:00:00Z --end 2028-01-01T00:00:00Z
```

Deploy persistent physical-series receipts and `metrics.npz` files with the terrain package and verified SPICE kernels. Native arrays are needed for detailed analysis; the metrics endpoint does not open them. Browser memory caches 100 prepared requests and ignores stale/aborted responses.

The prepared catalog band has since been extended to all years 2000–2100 at 20 m; see [century metrics preparation and evidence](century-metrics.md). The earlier [physical-series index report](../validation/lunarsight/metrics-chart-index-build.json) retains the baseline: 26 entries across 23 coordinates, including Site04 through November 2056, totaling 12,461,925 compressed bytes.

## Verification

[Earlier metrics-and-chart HTTP report](../validation/lunarsight/metrics-and-chart-http.json), reproduced for currently available coverage with:

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/verify_metrics_first.py \
  --output docs/validation/lunarsight/metrics-and-chart-http.json
```

Site04 metrics plus 800 preview bins: warm 10-year responses took 70–77 ms (the first cold response was 367 ms); 20-year responses took 109–135 ms, and 30-year responses 95–170 ms. Payloads are 368–401 KB. All 23 catalog points returned prepared 72-hour metrics and charts in 43–140 ms each; zero analysis jobs were created. These local timings measure prepared results, not full analysis or first-time source preparation.

The earlier [metrics-only baseline](../validation/lunarsight/metrics-first-http.json) recorded 26–40 ms warm responses without charts; it is retained as historical evidence.

An independent native scan after timing agreed with every indexed metric within 0.000081 seconds over the tested long windows. Differences arise from floating-point accumulation order. At the time of this baseline, an unprepared 50-year request returned 409 rather than endpoint-clamped values; the expanded prepared band now supports that range.

Weighted integrals of the displayed charts also match native Sun/Earth duration bounds and joint metrics within 0.000002 seconds in the measured long-window cases.

Tests block native reads and preview serialization and assert that metrics can still be fetched first. They cover unknown bounds, partial sunlight, cross-day runs, source changes, unsupported boundaries and corrupt indices. No LLM calls are used.

Final regression: 420 backend tests passed, one skipped; 47 frontend tests passed and the production build succeeded. Browser acceptance changed Site04 to a 30-year range and displayed metrics plus 800 bins in each of the three charts with METRICS READY, without submitting an analysis job.

The comparison project's [README](https://github.com/BroBYW/CLPS-Lunar-Mission-Website#how-it-works) documents a 2024–2030 browser-data band. Its [Ephemeris.sample](https://github.com/BroBYW/CLPS-Lunar-Mission-Website/blob/main/web/src/lib/astro.ts) clamps out-of-band samples to the first/last vector. This implementation preserves the requested UTC window and requires actual prepared coverage.
