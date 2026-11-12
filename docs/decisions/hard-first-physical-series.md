# Hard requirements first, reusable physical series, on-demand CSV

The default MissionRequest and coordinate Planning policy is `evaluation_policy: "hard_first"`. The existing `complete` policy remains available for diagnostic comparisons, including `scripts/planning_cli.py --evaluation-policy complete` and JSON requests. Both policies use the same native visibility algorithm, duration bounds, requirements, tolerances and decision gate. No mission-duration maximum was introduced.

## Execution order and hard failure evidence

1. Verify source evidence and terrain geometry; obtain initial native five-minute Sun/Earth/Joint samples. Publish initial metrics to asynchronous clients.
2. Check requested sunlight availability, then Earth availability, then contact requirements. A fractional hard failure requires the **upper** duration bound to fall below the requested minimum. Missing samples remain optimistic in that bound. An unknown-only interval does not become a proven failure.
3. At the first proven sampled hard failure, return FAIL, the evaluated prefix of `constraint_checks`, and `hard_failure`. The remaining validation and soft preferences are explicitly `skipped_hard_failure` in `evaluation_stages`, rather than incorrectly reported as passed or failed validation.
4. Otherwise perform the existing native 5/1-minute, radius, angular, quadrature and eligible refinement checks. Assess soft preferences after validation. Validation failure still withholds PASS; a soft preference failure does not reject the mission.

`hard_failure` records the failed requirement, threshold, optimistic/pessimistic observed bounds, whole-window duration shortfall where applicable, exact coordinate, analysis window and up to three supporting time intervals. Contact failures also retain contact metrics and the completion deadline when present. A dark interval contributes to a whole-window fractional shortfall; it is not presented as a single instant that alone proves the whole mission failed. Supporting intervals are ranked by integrated sunlight deficit (or blocked Earth duration); each retains its worst native sample. The UI can jump to that sample and request its exact values, avoiding tiny nearly full-disc numerical dips as the primary visual evidence.

The short-circuit is a rejection in the declared sampled model. It does not claim continuous-time or physical uncertainty certification. Corrupt input/checksum failures remain errors. A PASS still requires the existing full or conservative mission-path validation. `complete` retains the numerical diagnostic path even for a sampled hard failure.

## Physical cache

`data/cache/point-analysis/physical-series/` stores lossless binary visibility series independently of hard/soft requirements, contact rules and completed-result caches. Its identity includes the ephemeris kernel/provider identity, exact observer/site/height, visibility and solar-disc method versions, time-grid step, and the actual horizon content. Each entry declares its exact time coverage and SHA-256. Requests for exact aligned subwindows reuse a covering entry; missing coverage is calculated normally without interpolation, clamping or extrapolation.

Numerical comparison series also reuse physical samples when available. Requirement outcomes and current-window validation are reevaluated; a cached physical series never implies that a new requirement has a preapproved PASS. The legacy or synthetic ephemeris path without a verified shared-provider identity continues to use content-keyed in-memory reuse.

State/category columns use small integer codes with an explicit dictionary in the artifact reference, preserving float64 values and exact UTC timestamps. The reader reconstructs the shared V/B/? alphabet before comparing state series. Metadata in Pandas `attrs` is kept as immutable JSON strings because Pandas otherwise deep-copies nested receipt structures repeatedly during column access; profiling found that cost dominated display timeline/event construction in long cached requests.

## Deploy preparation

```bash
make ephemeris-prepare
make physics-prepare
# A different prepared band, site list, hardware pair or persistent root:
PYTHONPATH=backend backend/.venv/bin/python scripts/prepare_physical_series.py \
  --start 2026-01-01T00:00:00Z --end 2028-01-01T00:00:00Z \
  --sites Site01_P1 Site04_P1 --panel 20 --antenna 20 --workers 2
```

Run this during deployment preparation with the verified horizon package and SPICE kernels installed. Keep the resulting `data/cache/point-analysis/physical-series/` directory on persistent storage, or include it in the deployment data image at the same configured Point pipeline root. Runtime caches and kernels are intentionally not committed to Git. The default prepared band is **cache coverage**, not API mission coverage: dates outside it and different heights still use the normal pipeline and populate further entries.

[Preparation report](../validation/lunarsight/physical-series-build.json) covers all 23 default coordinates at 20 m panel/antenna, 210,240 native five-minute intervals each, over 2026–2028. The initial measured complete-band read times were roughly 0.12–0.38 seconds per point on the local machine. Additional physical-series entries consume disk space as new windows/configurations are calculated; this is not a globally precomputed lunar model.

## Remove CSV from completion latency

The committed source timeline is the lossless binary artifact. Normal analysis no longer writes a second, large `intervals.csv` before signaling completion. `GET /api/lunar/point/analyses/{job_id}/intervals.csv` verifies that artifact and streams CSV in chunks only when requested. Full native JSON remains available through the compatible full-result API, while the UI uses the bounded display result and exact-instant endpoint.

## Measured comparison

[Real-data report](../validation/lunarsight/hard-first-performance.json), reproduced with:

```bash
PYTHONPATH=backend backend/.venv/bin/python scripts/verify_hard_first_performance.py \
  --output docs/validation/lunarsight/hard-first-performance.json
```

The benchmark isolates completed-result caches, uses installed verified terrain/kernel data and a persistent physical cache, and compares `complete` with `hard_first` on the same physical request and hard thresholds. These are local timings rather than a deployment latency guarantee. Both final metric sets and FAIL decisions matched exactly.

| Case | Complete diagnostics | Hard-first | Initial metrics in hard-first |
| --- | ---: | ---: | ---: |
| Haworth, 72 h, sunlight ≥80%, 20 m | 1.14 s | 0.28 s | 0.24 s |
| Site04, 2026–2036, sunlight ≥99%, 20 m | 33.10 s | 3.11 s | 1.27 s |

Changing only Haworth's threshold took 0.28 s; a 24-hour subwindow reused the covering physical series and took 0.087 s. The ten-year complete run spent about 1.30 s committing binary artifacts, with no automatic CSV write. Faster rejection does not imply that a non-failing ten-year request can skip validation. It can display cached metrics first while those checks continue.

## Verification

The backend suite passed 415 tests (one skipped). The final soft-stage diagnostic consistency change also passed the 75-test point-analysis, hard-first, resolution and mission-unification subset. Frontend: 44 tests passed and the production build succeeded. Real API regression covered Point/Compare/Search, native CSV and official JPL angle comparisons without live LLM calls.

The browser acceptance case is Haworth, 2026-11-17 through 2026-11-20, 20 m, minimum sunlight 80%. It returns FAIL with a 72.90% optimistic bound and at least 5.11 equivalent full-disc hours short. Clicking the highest-deficit interval selects 2026-11-19T08:45:00Z; its exact native sample shows 11.8% of the solar disc visible.
