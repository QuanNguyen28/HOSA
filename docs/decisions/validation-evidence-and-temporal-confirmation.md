# Reusable numerical evidence and temporal hard-failure confirmation

Requirements still use the same sampled metrics: mean solar-disc fraction, Earth-centre LOS and contact windows. The five-minute metric response and prepared 2000–2100 charts remain available without starting evaluation.

## A hard rejection must agree across time grids

With `evaluation_policy="hard_first"`, a failed upper bound on the five-minute timeline now triggers a one-minute check of that same mission window. The same hard requirement must fail on both grids before returning early. Missing/unknown fine-grid evidence cannot confirm a failure. If the grids disagree, full validation continues; an unconfirmed coarse failure remains INDETERMINATE rather than becoming a final FAIL. This also applies to contact deadlines and to the coordinate/snapshot shared decision evaluator when the comparison is available.

Confirmed early failures return metrics, timeline, events and supporting samples from the one-minute timeline. `hard_failure.sampling_minutes=1` and `confirmed_sampling_minutes=[5,1]` identify the evidence. `validation.temporal_confirmation` retains both metric sets and checks. `validation.status="skipped_hard_failure"` means that full spatial validation/refinement and soft preferences were skipped after temporal confirmation, not that no one-minute calculation occurred. Both grids are sampled models; agreement does not certify continuous-time or physical DEM uncertainty.

## Cache evidence, reassess decisions

`data/cache/point-analysis/validation-evidence/` stores checksum-verified JSON evidence independently of thresholds, contact rules, soft preferences and final decisions. Keys include exact coordinate, hardware, UTC window, actual coarse/fine/radius horizon contents, provider/kernel hashes, model/method versions and quadrature configuration.

The standard evidence contains native metrics for each configuration, duration differences, event matching, angular comparisons, geometry/interpolation/quadrature checks and losslessly coalesced Earth-state runs. Those runs let each new contact requirement be checked for every alternative without reconstructing visibility. A cache hit loads the verified nominal physical timeline and skips ephemeris and visibility calculations for this stage. Missing native samples cause a rebuild; corrupt evidence fails with `VALIDATION_EVIDENCE_INTEGRITY_FAILED`.

Eligible mission-path envelopes are also cached as threshold-independent bounds and Earth-state runs. The current request's source/seam/coverage gates are checked before an envelope can authorize PASS. Requirements, including contact setup, count and deadline, are reassessed against these bounds. A previous PASS is never copied to a changed request. Refinement is still bounded by the existing two rounds, and each configuration has its own evidence key.

Responses expose `execution.validation_evidence_cache_hit`, `execution.mission_path_evidence_cache_hit`, `validation.evidence_cache` and, when relevant, `validation.mission_path.evidence_cache_hit`. A complete-result cache hit remains a separate case. Legacy `sun_center` numerical validation still follows its existing snapshot/Horizons path; shared-SPICE `solar_disc` uses the new persistent evidence products.

## Prepare an exact window before deployment

```bash
make ephemeris-prepare
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/prepare_validation_evidence.py \
  --request docs/examples/point-site04-evaluation-request.json \
  --all-refinements --report /tmp/hosa-site04-validation-prepared.json
```

The request uses the normal MissionRequest schema. Preparation clears hard thresholds/contact rules before evaluating the numerical configurations and stores no mission decision. It prepares the exact coordinate, hardware and time window, not validation for every possible subwindow of 2000–2100. Mission-path evidence is prepared on first eligible analysis and then reused. Omit `--all-refinements` to prepare only the initial 0.25/0.125-degree comparison.

Deploy `validation-evidence/` with compatible `physical-series/`, verified kernels and the terrain package on persistent storage. The existing century metrics-only product is separate and does not contain native one-minute validation data. No upper mission-duration limit or new feasibility tolerance was introduced.

## Verification

Tests exercise coarse FAIL/fine PASS, unknown fine evidence, availability/contact-deadline crossings, persistent reuse after changing sunlight/contact requirements, source/window invalidation, corrupted evidence, and cached mission-path bounds behind a newly failed seam gate.

[Real-data report](../validation/lunarsight/validation-evidence-reuse.json), reproduced with:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_validation_evidence.py \
  --output /tmp/hosa-validation-evidence-reuse.json
```

For Site04 over 1–4 March 2026 at 20 m, the initial evidence run took 0.52 s. Changed thresholds took 0.17–0.22 s; patched ephemeris, visibility and envelope builders proved that none were called again. A stricter requirement returned FAIL, a relaxed one PASS, and independent fresh evidence matched the reused result. A second real point confirmed hard FAIL on both grids. Prepared century metrics still returned 800 chart bins with evaluation not started. These are selected local measurements, not deployment latency or continuous-time guarantees.
