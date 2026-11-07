# LunarSight data EDA

NASA PGDA LOLA (MOON_ME/DE421); JPL Horizons, PROVISIONAL scenario.

| Raster | Shape | Pixel spacing (m) | Min (source unit) | Max (source unit) | NoData % |
|---|---|---|---:|---:|---:|
| Site01_dem | [3200, 3200] | [5.0, 5.0] | -523.183 | 1959.496 | 0.000 |
| Site01_error | [3200, 3200] | [5.0, 5.0] | 0.062 | 5.583 | 0.000 |
| Site01_count | [3200, 3200] | [5.0, 5.0] | 0.000 | 5.000 | 0.000 |
| Site04_dem | [3200, 3200] | [5.0, 5.0] | -2847.877 | 1805.073 | 0.000 |
| Site04_error | [3200, 3200] | [5.0, 5.0] | 0.064 | 7.635 | 0.000 |
| Site04_count | [3200, 3200] | [5.0, 5.0] | 0.000 | 5.000 | 0.000 |
| dem80 | [7600, 7600] | [80.0, 80.0] | -7295.517 | 7026.331 | 0.000 |
| dem240 | [7760, 7760] | [240.0, 240.0] | -9127.114 | 7024.770 | 0.000 |

| Horizons query | Received / expected | Missing UTC | Missing angles | Elevation (°) |
|---|---:|---:|---:|---|
| Site01_P1_sun_5min_cf2d5a7a2d1c | 4897/4897 | 0 | 0 | 0.9799 to 1.7743 |
| Site01_P1_earth_5min_0d1dd7e592f9 | 4897/4897 | 0 | 0 | -5.0510 to 5.8655 |
| Site01_P1_sun_1min_2b05fa08baa7 | 4321/4321 | 0 | 0 | 1.1719 to 1.4951 |
| Site01_P1_earth_1min_0e4b12e27d30 | 4321/4321 | 0 | 0 | -5.0510 to -1.3412 |
| Site04_P1_sun_5min_a9308b181ba5 | 4897/4897 | 0 | 0 | 1.3122 to 1.6057 |
| Site04_P1_earth_5min_8c1ffb6d6238 | 4897/4897 | 0 | 0 | -4.8481 to 6.0571 |

Exact windowed counts, moments and min/max, with systematic-sample percentiles in the manifest. Preview figures are downsampled by nearest neighbour; sparse NoData can be absent from previews. A 5 m spacing is not effective resolution. The count layer records LOLA shots, including zero at interpolated cells.
