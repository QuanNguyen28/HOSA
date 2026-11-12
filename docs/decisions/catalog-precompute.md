# Portable catalog geometry and display meshes

The prepared product covers the two scientific P1 points and the 21 exact coordinates in `manifests/compare-sites.json`. Coordinates are never snapped to a nearby site. The published manifest indexes content-addressed NPZ horizons and gzip JSON meshes with SHA-256 and byte counts. A site becomes visible only after its entire build is verified and atomically published.

## What is prepared

- Each of the 23 observers has horizons for 1, 2, 10 and 20 m above the native sampled DEM. Device heights can be combined without rescanning terrain.
- The 400 km scan uses 0.03125° rays; the separate 300 km scan uses 0.0625° rays. Runtime sensitivity grids are exact subsets of these rays, including both existing refinement rounds. No spatial/height interpolation is performed.
- Each observer has the 11 unique meshes requested by the pole and ground views. Two additional polar-cap display grids cover the globe view. These meshes preserve the original bilinear display transport and never supply scientific horizon calculations.
- GET mesh responses reuse the exact gzip artifact, expose ETag and a five-minute freshness period, and support conditional 304 responses. A bounded frontend promise cache deduplicates simultaneous requests and reuses recent responses across site/view switches.

## Scientific behavior

Builds use the existing native DEM scanner, source receipt verification, seam checks and independent Cartesian ENU blocker checks. The runtime rechecks NPZ hashes, native azimuth/height/radius metadata and independent ENU elevations before writing its usual geometry cache. Missing coverage flags and failed seam checks remain in the product; the existing radius, angular, temporal, quadrature and mission-path validation gates still determine the result. Precompute does not make a provisional result scientifically validated and does not guarantee a PASS.

An installed dataset with a new/changed source receipt invalidates the prepared product. Geometry/display method versions are also checked. With raw DEMs absent, the package can serve its declared scientific snapshot and prepared display meshes; source provenance remains the archived NASA hashes. Raw point terrain sampling and unprepared coordinates/heights still require the corresponding verified DEMs. Changed source files must be ingested with new verified receipts rather than retaining an old receipt.

## Deployment

Keep `data/processed/site-precompute/v1/manifest.json` and all referenced `blobs/` together in the backend deployment artifact. The default root is repository-relative; `HOSA_PRECOMPUTE_ROOT` can select another complete package. Do not commit local runtime caches or credentials.

```bash
make backend-install
make ephemeris-prepare
make backend-run
```

The official SPICE kernel preparation step is still required for solar-disc astronomy. Monthly shared vector tables are generated and cached on demand; they are independent of the terrain package. Provision writable persistent storage for `data/cache/` (or the configured display cache root `HOSA_DISPLAY_CACHE_ROOT`). Multiple instances may use separate local caches while sharing the same read-only prepared package. Full interval responses for multi-year missions, long-period visibility evaluation, browser mesh construction, network bandwidth and cold SPICE table creation still take time; precompute removes repeated native terrain scanning and display resampling.

To rebuild after ingesting new verified NASA DEMs or changing geometry code:

```bash
make precompute-catalog
# Restrict a rebuild or relocate its output if needed:
PYTHONPATH=backend backend/.venv/bin/python scripts/precompute_catalog.py --sites Site04_P1 --workers 1
PYTHONPATH=backend backend/.venv/bin/python scripts/verify_precomputed_catalog.py \
  --output docs/validation/lunarsight/catalog-precompute-acceptance.json \
  --base-url http://127.0.0.1:8001
```

The builder resumes compatible complete observers, verifies their referenced bytes, and requires verified raw sources to rebuild. Rebuilds do not download data or call an LLM. The acceptance script needs the original native Site01/Site04 scan fixtures for its independent regression comparison and local SPICE kernels for fresh-result benchmarks.

Evidence: [build report](../validation/lunarsight/catalog-precompute-build.json), [real-data acceptance](../validation/lunarsight/catalog-precompute-acceptance.json). Timings in that report are local measurements, not deployment latency guarantees.

Final acceptance verified all 184 profiles and 255 meshes (439 blobs, approximately 131 MiB on disk). The eight native Site01/Site04 comparisons had a maximum horizon difference of 0° and identical coverage flags. Fresh result and geometry caches, with the DEM scanner disabled, produced Site01 PASS in 0.52 s, Site04 PASS in 0.48 s and Haworth FAIL in 1.07 s for a 72-hour mission with an 80% mean solar-disc requirement and 20 m devices. A 300 km Site04 display request returned identical resampled elevations in approximately 15 ms over local HTTP, versus approximately 4.22 s for direct DEM resampling in the same acceptance run; gzip payload was 267,717 bytes and conditional reload returned 304. The original UI was also exercised through Analyze point at Site04 and showed the computed result and interval timeline. Full backend verification passed 404 tests (1 optional skip); frontend passed 40 tests and its production build. No live LLM inference was used.
