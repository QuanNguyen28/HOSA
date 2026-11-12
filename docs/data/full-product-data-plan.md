# LunarSight full-product data plan

Status date: 2026-11-12  
Registry: `manifests/lunarsight/full_product_sources.json`

## Data policy

- Scientific inputs come only from official NASA, JPL/NAIF, PDS, NASA GSFC
  PGDA and NASA/JPL Moon Trek endpoints.
- The competitor product is used only to identify useful product capabilities.
  Its generated binaries and scientific claims are not inputs to LunarSight.
- Raw assets are immutable. Every complete download has an exact URL, byte
  count, retrieval time and SHA-256 receipt.
- A user-selected coordinate is not declared safe merely because data exists.
  Coverage, uncertainty and scenario-dependent results remain separate fields.
- Multi-gigabyte cloud-optimized GeoTIFFs are accessed by byte range and saved
  as bounded site windows. This is reproducible and avoids unnecessary full
  raster downloads.

## Feature-to-data coverage

| Product capability | Raw/official input | Derived web data | Current state |
|---|---|---|---|
| Global 3D Moon | NASA SVS `moon_small.glb`, PDS `ldem_16` | optimized GLB, normal/relief texture | source registered; core acquisition enabled |
| South-pole map and arbitrary point | LOLA 80 m and 240 m DEM | polar basemap, sampled elevation | DEMs already installed and verified |
| Detailed local terrain | LOLA 10 m and 20 m COG | bounded site windows, terrain mesh/patches | remote COG registered; window materialization is on demand |
| Slope and roughness | LOLA DEM and morphology products | multi-scale slope, roughness and local statistics | morphology core sources registered |
| Data confidence | LOLA count, effective resolution and total error | confidence flags and uncertainty panel | core acquisition enabled |
| Sun illumination | DE440 SPICE, lunar orientation kernels, terrain horizon | ephemeris and illuminated intervals | kernels registered; long-range derivation pending |
| Earth line of sight | DE440 SPICE and terrain horizon | Earth visibility/contact intervals | kernels registered; long-range derivation pending |
| Validation overlays | PGDA solar/Earth visibility and PSR rasters | comparison layers and validation report | core acquisition enabled |
| Mast-height planner | terrain horizon at 2/5/10/20/30/50 m | mast scenario cube | derivation pending |
| Candidate regions | NASA Moon Trek Artemis region polygons | unassessed region GeoJSON/CSV | source and deterministic builder implemented |
| DSN contact context | SPICE and published DSN complex coordinates | hourly DSN visibility grid | derivation pending |
| LRO photo comparison | PDS LROC WAC south-pole frames | selected, cited site/date crops | on-demand; must be throttled |
| Site comparison/search | all validated derived metrics | compact columnar/binary index | pending after long-range derivations |

## Acquisition profiles

### Core

Approximately 825 MiB was missing at the start of the 2026-11-12 run. It
contains SPICE kernels, LOLA quality rasters, PGDA validation maps, morphology
overviews, the PDS global relief grid and the NASA SVS web Moon model. Existing
80 m and 240 m DEMs are verified but not downloaded again.

### Extended

Adds the 20 m PSR model (about 147 MiB). It is useful for resource/PSR context
but is not necessary for the first complete interactive build.

### On demand

Includes LROC photo crops and remote 10 m/20 m DEM windows. These are selected
by approved site or user coordinate. Full archives are not mirrored locally.

## Reproducible commands

```bash
make data-plan
make data-acquire
make data-verify
make data-sites
```

Acquire the extended PSR layer separately:

```bash
backend/.venv/bin/python scripts/acquire_full_product_data.py --profile extended
```

## Required next derivations

1. Materialize 10 m/20 m DEM windows for the approved catalog and implement an
   on-demand window cache for arbitrary clicks.
2. Generate hourly SPICE Sun/Earth vectors for the supported mission period,
   then validate sampled epochs against JPL Horizons.
3. Compute horizon masks and mast-height variants from the multi-resolution DEM
   stack; retain three-state visibility (`true`, `false`, `unknown`).
4. Produce terrain patches, basemap tiles, compact ephemeris, visibility and
   comparison indices for frontend delivery.
5. Run numerical sensitivity, seam, duration-bound and independent-reference
   validation before any dataset is marked scientifically releasable.
