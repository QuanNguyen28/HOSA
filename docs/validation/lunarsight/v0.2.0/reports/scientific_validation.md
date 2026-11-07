# Scientific validation

Run status concerns the data pipeline. All scenario-dependent results are provisional. Visibility is geometric for the sampled Sun/Earth centres.

| Check | Status | Detail |
|---|---|---|
| synthetic_tests | PASS | 17 passed, 2 warnings in 1.26s |
| source_Site01_count | PASS |  |
| source_Site01_dem | PASS |  |
| source_Site01_error | PASS |  |
| source_Site01_roi | PASS |  |
| source_dem240 | PASS |  |
| source_dem80 | PASS |  |
| source_p78_readme | PASS |  |
| dem80_eda | PASS |  |
| dem240_eda | PASS |  |
| Site01_site_catalog | PASS |  |
| Site01_dem_eda | PASS |  |
| Site01_ephemeris | PASS |  |
| Site01_geometry | PASS |  |
| Site01_visibility | PASS | Executed under the provisional scenario; sampled model only |
| Site01_sensitivity | PASS | Measured both angular steps, both time steps and both radii; tolerance values provisional |
| Site01_pipeline | PASS |  |
| source_Site04_count | PASS |  |
| source_Site04_dem | PASS |  |
| source_Site04_error | PASS |  |
| source_Site04_roi | PASS |  |
| Site04_site_catalog | PASS |  |
| Site04_dem_eda | PASS |  |
| Site04_ephemeris | PASS |  |
| Site04_geometry | PASS |  |
| Site04_visibility | PASS | Executed under the provisional scenario; sampled model only |
| Site04_pipeline | PASS |  |

See pytest.log for synthetic cases, source_manifest.json for provenance, seam reports and sensitivity.json for actual measured convergence. Reference check recomputes sampled real blockers via Cartesian-to-ENU geometry; it is not an independent Moon Trek/CMS comparison. G0 thresholds and scenario epoch await review.
