# HOSA current system context

Status: current working-tree reference. For a factual detail, verify the linked manifest or implementation before editing scientific behavior.

## What the project answers

HOSA estimates whether a specified lunar surface observer and mission time window meet illumination and geometric line-of-sight requirements to Earth's center. Terrain horizons and NASA LOLA/PGDA terrain data describe obstruction; JPL Horizons supplies Sun/Earth geometry. The deterministic engine owns measurements, candidate ranking, validation, and PASS/FAIL/INDETERMINATE. LLM output explains the project and the engine's result; it never creates scientific metrics or changes a decision.

This is a research and planning prototype. It is not landing-site certification, a power or thermal model, or a radio link budget.

## Current observer and ephemeris coverage

The precomputed P1 observers are exactly `Site01_P1` (Connecting Ridge) and `Site04_P1` (Shackleton Rim), as listed in `manifests/sites.csv`. Cached JPL Horizons replies, receipts, and derived series belong to those explicit observer IDs and data epochs; they do not prove ephemeris coverage for every NASA region, coordinate, or future time. Do not call these `Site01` and `Site02`, and never transfer a receipt or response between observer IDs.

The current mission API also accepts coordinates, a duration or explicit UTC end date, and mission-specific contact requirements through `MissionRequest` in `backend/app/mission/models.py`. Durations have no application maximum and use exact 5-minute increments with a minimum of 1 hour. The precomputed snapshot remains fixed at 72 hours; other durations use verified coordinate analysis. Those inputs go through the coordinate analysis pipeline and its coverage/validation checks. Their availability depends on the actual data and capabilities; a catalog entry alone is not a computed result.

## Dataset catalog and limits

`REGION_INVENTORY.json` lists 27 NASA PGDA region/version entries and the assets observed in the delivery. It is an inventory, not proof that every asset is installed, valid for a given coordinate, or scientifically evaluated. `Site06`'s ROI source link is broken and the ROI asset was not found. `Site20` and `Site20v2` share a site group. Preserve source checksums, coordinate reference system, units, pixel registration, and nodata meaning. Never synthesize missing ROI or infer point coverage from a broad DEM.

The NASA assets and receipts are indexed as metadata. Large ZIPs, DEM rasters, point clouds, and full timelines must be read or summarized by the backend when a numeric answer is needed; do not put them into an LLM prompt. XYZ values in the delivered `.xyzi` format are kilometres and the fourth column is RDRid.

## Source priority

For current behavior, use the current backend schemas and code, `manifests/sites.csv`, `manifests/datasets.csv`, the current HOSA source manifest, and verified NASA/JPL receipts. `docs/submission/`, the OpenRouter-era LLM decision, and v0.2.0 validation notes describe historical state and must not override newer manifests, code, or v0.3.0 validation. Cite the exact passage used, and say when the requested fact is not present in the retrieved current sources.

## Merged computing and chat behavior

The Compare catalog and named-site aliases from `manifests/compare-sites.json` are shared with chat. Named catalog coordinates are not interchangeable with the distinct P1 snapshot observers. Planning chat retains an evaluated duration and target across turns; it can accept `mission_end_utc` for an explicit mission end.

With `resolve_indeterminate=true`, the engine first checks conservative sampled mission-path bounds and refines only if needed. A hard requirement failure remains FAIL even when validation has warnings. A PASS can have full `validation.passed=false` with `validation.mission_path.passed=true`; explain the requested scope and provisional empirical bounds, never claim full-circle or physical DEM certification. Missing data, seam or ENU failures still block this fallback. Request-specific locks and separate short/long job workers preserve interactive computation.
