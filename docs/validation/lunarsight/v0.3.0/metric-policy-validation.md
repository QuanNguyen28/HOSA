# Availability hard / continuity soft — validation

Date: 2026-11-10. Dataset v0.3.0; policy
`availability-hard-continuity-soft-v1`; planning schema 2.0.

The new snapshot derives both total Sun and total Earth-LOS bounds from the
existing V/B/? intervals. All 2,688 mission windows were independently checked
by summing clipped interval seconds for Earth V and V-or-?, then comparing the
stored lower/upper totals and default Earth requirement decisions. Geometry and
ephemeris input bytes are inherited unchanged; source/output checksums are
recorded in `data/processed/lunarsight/v0.3.0/derivation.json`.

Regression checks cover all nine Sun/Earth state combinations, irregular weights,
unknown duration bounds, equality at minimum thresholds, required hard inputs,
soft FAIL/INDETERMINATE not overriding hard PASS, hard FAIL not rescued by soft
preferences, soft tie-breaking, search filtering, exports and assistant follow-up
inheritance of the Earth-LOS minimum. Sensitivity distinguishes a hard decision
change from a soft-only preference change on the exact request window.

The live localhost CLI/API check passed compare, search and CSV export using a
real Site01 window with hard PASS and soft blackout FAIL; missing hard minima
were rejected. Frontend typecheck and production build passed. The build also
reported the pre-existing Node 18 / Vite Node-version warning.

After the downloaded Site01/Site04 DEMs were discovered in `data/raw/nasa`, the
full backend suite passed: **188 passed, 1 skipped**. The remaining skipped test
requires a completed regional 80 m DEM. Both local 5 m DEMs were verified against
official source receipts (byte count, SHA-256) and sampled at their P1 coordinates:

| DEM | SHA-256 | P1 elevation (m) |
| --- | --- | ---: |
| Site01 | 3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e | 1958.3211669921875 |
| Site04 | 38ff70dbdf2f066c2cfa94a646c3a59d653ce7f6b4528b15fc1b43ee397ce758 | 1737.9921875 |

Raw files were not moved or modified. Terrain discovery supports both the older
site/global directories and the current flat NASA download directory; `.part`
files remain unavailable. Regional downloads were still in progress at this
validation point. No incomplete regional file was used as scientific input.

All conclusions remain provisional and limited to the sampled model. The new
aggregation does not add a power/thermal model, an RF link budget, a continuous
time uncertainty bound, or landing certification. The 80% UI defaults are editable
demonstration choices, not NASA mission requirements. Historical v0.2.0 policy
outputs are retained and are not relabeled as v0.3.0 results.
