# HOSA data pipeline

Pipeline for two NASA LOLA south pole ROIs and Sun/Earth centre ephemerides. The scenario beginning 2026-11-14 00:00 UTC and the G0 tolerances are **PROVISIONAL**. A passing job means the sampled pipeline ran for its input configuration; it does not approve the epoch, model tolerances, or any operational interpretation.

## Kaggle

1. In a **Private** CPU Python notebook, import `notebooks/lunarsight-data-pipeline.ipynb` via **File → Import Notebook**. This notebook includes the source files, config and synthetic fixtures, so no third-party upload or dataset attachment is needed.
2. Enable **Settings → Turn on internet**. In the Draft session, execute each code cell in order and wait for its output. Download `/kaggle/working/lunarsight-data-deliverables.zip` before ending the session. Review `reports/execution_status.json` for the scientific stage results.
3. Confirm the provisional epoch and tolerances separately with science/QA. To select another epoch, edit all three UTC boundaries consistently in `config/scenario.json`, rebuild the embedded notebook using `src/build_notebooks.py`, and rerun.

The four numbered notebooks support collection, DEM EDA, ephemeris EDA, and validation. The combined notebook is the self-contained end-to-end runner. Numbered notebooks share a working tree, with the directory selected by `LUNARSIGHT_ROOT` when set. In separate Kaggle sessions, use the combined notebook.

## Local rerun

Extract the ZIP, change into the `lunarsight-data` directory, and use Python 3.11+:

```sh
python -m pip install -r requirements.txt
python src/pipeline.py
```

The pipeline requires free CPU, ~1 GiB free space for raw NASA data and access to the official NASA/JPL endpoints. It downloads Site04 only after Site01 passes its gates. Original DEMs and ROI archives are excluded from the ZIP; use the URLs and SHA-256 in `manifests/source_manifest.json` to verify a redownload. Retain downloaded files and adjacent receipts to run again with `python src/pipeline.py --offline`. The raw Horizons results, query configuration and receipts are included. Use a fresh output directory for a new epoch or geometry configuration.

## Method and limits

- Spherical three-dimensional ENU, true geographic north, east-positive longitude, ray sampling at ≤ half of the source pixel spacing and explicit comparison across DEM seams. If the fixed near seam fails, a seam following the 5 m footprint must meet the same limit on two interleaved azimuth grids. No additional planar curvature correction.
- PGDA 78 GeoTIFF metadata and LOLA RDR lineage determine the input geometry; JPL observer radii and frame are independently checked before combining. Coordinates in the catalog refer to the Moon.
- Coverage is finite in distance and sampling resolution. RMS error and LOLA spot count describe input quality; neither is a probability or an error bound. The sampled angles omit the solar disk, eclipses, electrical and RF models.
- Time intervals are half-open. Missing observations remain unknown. The last ephemeris row closes the final interval. The Sun/Earth timelines use different device heights. Constraint limits 12 h darkness / 6 h Earth-centre blackout are proposal examples.

Attribution: [PGDA 78](https://pgda.gsfc.nasa.gov/products/78) / Barker et al. 2021 [DOI](https://doi.org/10.1016/j.pss.2020.105119); [PGDA 90](https://pgda.gsfc.nasa.gov/products/90) / Barker et al. 2023 [DOI](https://doi.org/10.3847/PSJ/acf3e1); [JPL Horizons](https://ssd-api.jpl.nasa.gov/doc/horizons.html).
