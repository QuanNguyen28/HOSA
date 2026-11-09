# Site01 web terrain derivatives

Immutable source:

- `data/raw/Site01/Site01_final_adj_5mpp_surf.tif`
- Source SHA-256: `3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e`
- NASA PGDA/LOLA Site01 adjusted surface DEM
- Source bounds: X `[-19000, -3000]` m, Y `[-20000, -4000]` m
- Native raster: `3200 × 3200`, 5 m/pixel, Float32 elevation metres
- Source elevation range: `[-523.1834106445312, 1959.496215820312]` m

Web derivatives generated 2026-11-09:

| File | Derivation | SHA-256 |
| --- | --- | --- |
| `site01_height.png` | GDAL translate to 1024 × 1024 Byte PNG, linearly scaled from the source elevation range to `[0,255]` | `5e1920c69c38ed0b44b89c19dce0fd74da69946f757c6e7ff0b36717fc3b10a6` |
| `site01_hillshade.jpg` | GDAL hillshade, azimuth 315°, altitude 38°, edge computation; resized to 1024 × 1024 JPEG quality 92 | `799f1785bbfd06152c362f73e0f1fd5264646a0d8d73f3e2526cf73345f47eb8` |

These files are rendering derivatives. Scientific calculations continue to use the native Float32 DEM.

## Site04

Immutable source:

- `data/raw/Site04/Site04_final_adj_5mpp_surf.tif`
- SHA-256: `38ff70dbdf2f066c2cfa94a646c3a59d653ce7f6b4528b15fc1b43ee397ce758`
- Native raster: `3200 × 3200`, 5 m/pixel, Float32 elevation metres
- Source elevation range: `[-2847.877197265625, 1805.072631835938]` m

| File | Derivation | SHA-256 |
| --- | --- | --- |
| `site04_height.png` | GDAL translate to 1024 × 1024 Byte PNG, linearly scaled from the source elevation range to `[0,255]` | `e5476b035d519f5a629f1cbe2c647dbc9b20e307d5ce8a6c1999d531b5209129` |
| `site04_hillshade.jpg` | GDAL hillshade, azimuth 315°, altitude 38°, edge computation; resized to 1024 × 1024 JPEG quality 92 | `b7c648b0c1be1fe2f0686a410a1633b0904833837e965da043817ac92c583af7` |
