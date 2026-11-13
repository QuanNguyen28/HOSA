# Prepared metrics for viewer heights

The default catalog contains 19 coordinates. The archived `Site01_P1`, `Site04_P1`, `example-a` and `example-b` targets remain explicitly addressable by the API, but are excluded from the default selectors. Similar place names do not imply equal coordinates; the viewer must not substitute a P1 analysis for a different named catalog point.

Viewer presets set **both** panel and Earth antenna height: Lander = 2 m, then 10 m, 20 m and 30 m. The coordinate MissionRequest contract accepts positive heights through 30 m. Arbitrary intermediate heights and unequal panel/antenna pairs still need their own geometry/metrics and are not covered by these four prepared presets.

Each default coordinate has independent horizon profiles at 1/2/10/20/30 m. The additional 30 m profiles use the existing DEM source inventory, observer elevation and spherical ENU method, at 400 km / 0.03125° and 300 km / 0.0625°. Their blocker angles are independently verified before atomic publication. Existing profile blobs and display meshes are preserved. Missing terrain remains unknown; the new heights do not relax validation gates.

Each of the 76 default coordinate/preset configurations has nominal five-minute metrics and up to 800 chart bins for `[2000-01-01, 2101-01-01)` UTC. Source identity includes the actual height and profile hashes. No 20 m metric is copied to another preset. Requirement decisions and validation are still assessed for the specific mission request; the prepared metric endpoint starts no evaluation job and supplies no PASS/FAIL.

Reproduce on a machine with verified shared ephemeris installed:

```bash
make metrics-century-prepare
```

The committed terrain package can serve these heights without a raw DEM scan. To extend an older compatible terrain package in place, install its original verified DEM sources and run `make viewer-horizons-prepare` first. A source/observer mismatch must be investigated or rebuilt, rather than mixing new horizons into an old observer record.

The century builder supports incremental checkpoints and explicit selections:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/prepare_long_range_metrics.py \
  --sites haworth --viewer-heights 2 10 20 30 --workers 2 \
  --report /tmp/haworth-viewer-cache.json
```

Metrics caches under `data/cache/point-analysis/prepared-metrics/` are runtime artifacts excluded from Git. Deploy compatible caches on persistent storage or run the preparation command before routing traffic. Rebuilding the frontend alone does not create them.

Verify the running API with all 76 full-band configurations and three native windows per configuration:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_long_range_metrics.py \
  --viewer-heights 2 10 20 30 --base-url http://127.0.0.1:8001 \
  --output /tmp/viewer-metrics-http.json
```

Checks cover exact coverage boundaries, UTC leap days, chart-integrated hours, native Sun/Earth/Joint metrics, distinct height identities, monotonic terrain visibility with increasing height and absence of new analysis jobs. Local HTTP timings are measured separately from preparation time.

## Recorded verification

The prepared default cache contains 76 distinct source identities and 807,448,320 native five-minute intervals across all configurations. Compact aggregate and yearly indexes occupy about 1.76 GiB, excluding kernels, receipts and archived target caches. [Build report](../validation/lunarsight/viewer-metrics-build.json).

All 76 full-band HTTP configurations and 228 independently calculated native windows passed, including chart integrals and visibility monotonicity across all four heights. [HTTP/native report](../validation/lunarsight/viewer-metrics-http.json). The terrain package passed verification of 222 profiles and 255 meshes, including its four archived targets: [package report](../validation/lunarsight/viewer-catalog-verification.json).
