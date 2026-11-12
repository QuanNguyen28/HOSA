---
name: lunar-dem-eda
description: Inspect lunar DEM geometry, quality rasters and ROI membership. Use for LOLA raster EDA, lunar pixel registration, or site catalog generation.
---

# lunar-dem-eda

Inputs: validated LOLA DEM, NASA ROI, source metadata and optional count/error layers. Outputs: full raster metadata, quality summaries, real preview maps and a vetted site catalog. Use Rasterio, PyProj, GeoPandas, Shapely and NumPy.

1. Read the [PGDA README](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/README) and [LOLA RDR specification](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/document/rdrsis.htm). Distinguish projected CRS from the vertical datum; corroborate radial elevations from source lineage. Never substitute an Earth CRS.
2. Use registered pixel centres and verify two independent polar stereographic references and forward/inverse round trips. Inspect scale, offset and masks before taking statistics. Label effective resolution separately from spacing.
3. Open the ROI archive safely, reconcile CRS, snap a representative interior point to a valid pixel centre and retest polygon membership. Preserve the ROI record, row/column and dataset digest.
4. Compute finite moments window by window using [Rasterio windows](https://rasterio.readthedocs.io/en/stable/topics/windowed-rw.html). Label approximate percentiles and preview sampling. Distinguish valid zero count from nodata. Fail if CRS, scale/units, ROI membership or read integrity cannot be established.

Project workflow: `scripts/notebooks/02_dem_eda.ipynb`, `backend/app/point_analysis/`, `backend/app/services/lunarsight/point.py`, and `scripts/prepare_point_data.py`. The catalog and analysis service are separate: do not infer point-analysis coverage merely from a regional archive. Verify with synthetic affine/mask tests plus a receipt-verified real ROI/DEM when available.
