# Moon Trek observational imagery

Orbit and South pole have two surface appearances. NASA imagery shows archived
LRO/LROC observations served by NASA/JPL Moon Trek. Sunlight simulation retains
the existing time-dependent renderer. Recorded image shadows never represent
the selected mission time. The scientific DEM, horizons, ephemerides, metrics
and validation services do not consume imagery.

The verified source registry is `manifests/lunarsight/moontrek_imagery.json`.
It records capability hashes, native resolution, actual served tile matrices,
coverage and source URLs. Global WAC uses equirectangular lunar coordinates.
Polar WAC and NAC use south-polar stereographic metres on a 1,737,400 m sphere.
The polar WMTS advertises EPSG:0 and an invalid geographic-looking bounding-box
label: its product catalog and projection define the actual lunar CRS. Do not
interpret those metre extents as longitude/latitude or Earth Web Mercator.

Orbit loads a bounded camera-dependent quadtree over the two global root tiles.
Its displacement map is the existing LOLA display product with the same sphere
UV alignment. Parent tiles remain visible while finer imagery loads. Polar
terrain materials assemble at most 16 tiles per existing terrain LOD, choosing
NAC only when the complete window is within its footprint, otherwise polar WAC.
Terrain vertices and scientific coordinates remain unchanged. NAC's native
product is 1 m/pixel; this WMTS's finest served grid is approximately 2.09 m/pixel.
The NAC mosaic is uncontrolled and manually tied to WAC; display alignment is
not a scientific geolocation or terrain-validation measurement.

`GET /api/lunar/imagery/layers` returns the registry. Tile requests use
`GET /api/lunar/imagery/{layer}/{level}/{row}/{column}`. Only registered NASA
HTTPS tile URLs and valid matrix indices are accepted. The application pools
six connections, validates image signature/completeness and dimensions, and
publishes cached bytes and SHA-256 receipts atomically. Verified cache hits do
not require NASA access; HTTP ETag/304 supports browser reuse. Missing/invalid
upstream tiles are explicit errors. The UI retains local preview or a loaded
parent and labels incomplete imagery rather than claiming full-resolution data.

The frontend bounds decoded-image retention and concurrent/queued downloads.
GPU textures and geometries are released when their consumers unmount. Original
source bytes remain in ignored `data/cache/moontrek/`; credentials are not used.

Validation: `pytest tests/test_moontrek_imagery.py tests/test_point_analysis.py
tests/test_precompute.py`; `npm --prefix frontend test`; `npm --prefix frontend
run build`. Live checks include WAC/NAC responses through the frontend proxy,
verified cache hit and 304, visual inspection of both views, and switching back
to the existing sunlight simulation.

Source documentation: https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=moon
