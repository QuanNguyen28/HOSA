# NASA south-pole default observers

The default UI and deterministic request catalog use all 27 rows of NASA
ACD-50044 Revision A, Table A2-2 (pages 57–58). The source CSV and PDF receipt
are in `manifests/nasa-south-pole-sites.*`. The CSV was checked against the
rendered original pages. `scripts/build_nasa_default_catalog.py` generates
`manifests/compare-sites.json` reproducibly and preserves archived targets
outside the default list.

Published polygon-centre coordinates remain unchanged. No highest-point
optimization or snap to a DEM pixel changes the observer. Elevation is sampled
from the verified DEM at that coordinate; exact coordinate provenance does
not assert terrain quality, illumination, landing suitability or mission PASS.

UI labels use full place names. Source codes are metadata/API aliases, with
explicit `Site01_P1`/`Site04_P1` reserved for archived observers. Generic
`Site01` and `Site04` identify NASA's published region centres. Removed CLPS,
contrast and example choices remain explicitly addressable outside defaults.

Site20 and Site20v2 have the same published centre and location group. They
remain two named rows (the latter is labelled “extended boundaries”), sharing
one physical observer cache. Thus 27 rows require 26 coordinate products and
104 equal-height configurations at 2/10/20/30 m, not 108 separate computations.
The five prepared horizon heights remain 1/2/10/20/30 m for API compatibility.

Rebuild from verified NASA PGDA78 local 5 m DEMs and PGDA90 regional 80/240 m
DEMs. Missing or changed sources must invalidate incompatible derived data.
Hashes, reference checks, unknown terrain sectors and the existing scientific
validation gates remain part of the products. Metrics and charts cover
`[2000-01-01, 2101-01-01)`; scientific mission evaluation is still on demand.

The previous 19-point mixed catalog is not the definition of these published
centres: some of its Artemis points were selected by a highest-elevation
search and its literature points had different observer coordinates. A
matching display name does not justify copying those horizons or metrics.

Pole/Ground camera axes are local terrain zenith and north. On entering a
local view, reset inherited Trackball roll and initialize in this frame.
Time, Sun/Earth position and viewer-height changes do not reset navigation.
