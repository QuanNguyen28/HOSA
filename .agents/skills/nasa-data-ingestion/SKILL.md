---
name: nasa-data-ingestion
description: Acquire official NASA PGDA LOLA rasters and ROI archives with byte-level provenance. Use for lunar DEM, count, or uncertainty downloads and cache validation.
---

# nasa-data-ingestion

Inputs: NASA product page, exact asset URL and local storage budget. Outputs: original files and receipts, SHA-256, inventory, errors. Use Requests and Rasterio.

1. Resolve asset URLs from PGDA [78](https://pgda.gsfc.nasa.gov/products/78) and [90](https://pgda.gsfc.nasa.gov/products/90). Pull the 5 m DEM, ROI, count and RMS error first; skip clones unless needed. Read the [README](https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/README).
2. Check disk before transfer. Write to a temporary path; verify host, payload signature, full byte count and TIFF readability. If a COG stream truncates, request bounded byte ranges, require HTTP 206, validate Content-Range and stable identity headers, and hash concatenated bytes in order.
3. Keep raw files immutable. Verify a cache hit against source URL, byte count and SHA-256; fail closed if the receipt is missing. Never turn a partial file or HTML error into a dataset.
4. Record acquisition UTC, source/final URLs, byte count and checksum. Return actual downloaded assets and explicit failed/blocked rows; a discovered URL is not an acquired file.

Project workflow: `scripts/notebooks/01_data_collection.ipynb` plus the receipts and manifests in the immutable delivery folder; inspect `scripts/prepare_point_data.py` before preparing runtime copies. The delivery archive is not the engine catalog by itself. Preserve source receipts and do not relabel unavailable data. Site06 ROI is unavailable from the source delivery; Site20 and Site20v2 refer to the same location group. Verify importer changes with archive checksum, traversal, missing-receipt, byte-count, and cache-hit cases before using a real Site01 asset.
