# Initial metrics before scientific evaluation

The later [metrics-first path](metrics-first.md) adds indexed metrics for catalog browsing before starting an analysis job. Job previews now publish small metrics-only JSON before native preview serialization and display aggregation.

The asynchronous Point API publishes a preview after the native five-minute Sun/Earth ephemerides and baseline horizon visibility are available. The same job then performs one-minute ephemeris comparisons, angular/radius sensitivity, quadrature checks, hard/soft/contact requirements and any allowed refinements. No scientific decision policy or mission-duration limit was changed.

Preview responses have `evaluation_status: "pending"`, `decision: null`, `nominal_sampled_decision: null` and empty constraint checks. Their Sun/Earth metrics and `joint_hours` describe the initial sampled model. The UI displays these values with `EVALUATING` and keeps polling. Final metrics can differ if refinement selects a different horizon. Cached completed results can be returned immediately without a preview. If background evaluation fails, the available initial metrics remain visible alongside the error, with no final PASS.

## API flow

1. `POST /api/lunar/point/analyses` with the existing MissionRequest schema returns a job ID.
2. `GET /api/lunar/point/analyses/{job_id}` reports the stage and `preview_url` when initial metrics are ready.
3. `GET /api/lunar/point/analyses/{job_id}/preview` returns initial metrics and a bounded display timeline while validation continues. This never becomes a completed-result cache entry.
4. Once the job succeeds, `GET /api/lunar/point/analyses/{job_id}/result?view=display` returns the final result with at most 800 display intervals.
5. `GET /api/lunar/point/analyses/{job_id}/interval?at_utc=2031-11-24T00:02:00Z` returns the exact native interval containing that instant, during either preview or completed phases. UTC must include a timezone; mission intervals are half-open, so the exact mission end is outside the interval domain.

The original `/result` and direct `POST /api/lunar/point/analyze` endpoints default to the full native timeline for API compatibility. Direct callers can select `POST /api/lunar/point/analyze?view=display` to avoid downloading a full multi-year timeline.

## Why multi-year requests failed in the browser

A completed request from 2026-11-24 through 2035-11-24 generated about 597 MiB of JSON. The old UI downloaded and parsed that entire native timeline before aggregating it for display. The computation succeeded on the server while the browser received an impractically large response.

New result caches store a bounded JSON presentation plus a lossless structured NumPy timeline (`allow_pickle=False`). Full native rows remain available to API callers; exact instants use a memory-mapped binary search and artifact checksum. The compact representation is selected before any million-row JSON is built in the asynchronous job. The cache identity includes the transport schema version so old oversized cache entries are not reused in the new UI.

Aggregated bins retain duration-weighted fraction bounds and are explicitly marked `aggregated: true`. Mixed native states stay mixed/unknown in display, and the UI never presents an aggregate as the current native state or angle. Sun/Earth metrics and `joint_hours` are calculated on native intervals, independently of display bins. All validation still uses the original native 5/1-minute samples. Local source and ephemeris coverage still apply; there is no application maximum mission duration.

## Verification

`tests/test_progressive_analysis.py` checks preview delivery before a blocked validation step, null decisions while pending, background failure with retained metrics, agreement between full and display results, exact half-open intervals, irregular duration weights, corrupted binary artifacts, and bounded transport for over one million five-minute intervals spanning ten years. Frontend tests check preview ordering, failure delivery and rejection of aggregated bins as exact instants.

Real-data/UI acceptance uses Site04_P1, 20 m devices, an 80% mean solar-disc requirement, and 2026-11-24 through 2036-11-24 (87,672 hours; 1,052,064 native five-minute intervals). The UI displayed initial Sun 87.18%, Earth 52.78% and Joint 48.46% while one-minute ephemeris/validation was running. [Machine-readable acceptance](../validation/lunarsight/progressive-ten-year.json) records the final validation, display payload size, exact instant checks and equality of duration-weighted display integrals to native metrics.

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/verify_progressive_analysis.py \
  --base-url http://127.0.0.1:8001 \
  --output docs/validation/lunarsight/progressive-ten-year.json
```

The optional `--job-id` monitors an already submitted UI job. Timings in that mode start when monitoring begins; they do not measure submission-to-preview latency. No live LLM calls are used.

Final verification: 409 backend tests passed (1 optional Site06 skip), 43 frontend tests passed, and the production build/typecheck passed. Real Point/Compare/Search/CSV PASS/FAIL cases and eight native JPL comparisons passed again. The ten-year final UI payload was 1,123,065 bytes and its weighted display integrals matched the native Sun/Earth/Joint metrics. The final decision was INDETERMINATE because angular/time sensitivity and solar-disc quadrature checks did not pass; this scientific result was displayed successfully rather than treated as a transport failure.
