# Provenance and data quality

- NASA [PGDA 78](https://pgda.gsfc.nasa.gov/products/78) and [PGDA 90](https://pgda.gsfc.nasa.gov/products/90); [Horizons](https://ssd-api.jpl.nasa.gov/doc/horizons.html).
- Full original raster SHA-256 is in source_manifest.json, with raw HTTP provenance. No raw DEM is repackaged. Count and RMS uncertainty use their own source units.
- Raster CRS is checked against a Moon sphere of 1,737,400 m and independent south polar stereographic equations at two reference points. No Earth CRS substitution.
- WKT describes projection geometry; vertical datum follows the LOLA radial height source lineage, not merely the projected CRS. The Horizons response independently reports three matching reference radii, east-positive longitude and high-precision Mean Earth. Apparent Sun/Earth centre angles are airless.
- Native registered pixel centres are recovered from the corner affine once. Nearest pixel terrain sampling; explicit 5/80/240 m seam comparisons, no fitted vertical bias. A fixed near seam that fails the same tolerance is replaced only when a footprint-following seam (275 m inset) passes at two angular phases.
- GeoJSON-shaped site catalog carries a lunar coordinate declaration; do not load as terrestrial WGS84.
- DEM error is RMS, not a bound or a propagated probability. The finite-radius model, smoothing, subpixel relief and temporal sampling limit interpretation.

- Site01_P1: longitude 222.90402193°E, latitude -89.43892646°, height 1958.321 m; ROI Site01_ROIs:0.
- Site04_P1: longitude 203.73378626°E, latitude -89.77979956°, height 1737.992 m; ROI Site04_ROIs:2.
