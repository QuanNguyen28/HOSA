# Time-mean solar-disc illumination and shared ephemeris

Decision: 2026-11-12, `feat/merge-fe-be`.

## Requested behaviour

Default Point, Planning and new chat operations evaluate the **time mean of the
visible solar-disc area fraction**, including terrain occlusion and solid-Earth
occultation. The user explicitly selected this interpretation of the sunlight
requirement. Half a disk throughout a 100-hour mission gives 50% illumination,
or 50 equivalent full-disc hours; it fails a minimum of 80%.

`min_sunlit_fraction` retains its API name. `metrics_hours.total_sun_hours` is a
compatibility key for the integral of disk fraction, not the duration for which
any part of the Sun is visible. The response's `illumination` block and CSV
columns declare the model and definition. Earth LOS remains centre visibility.
Darkness means no solar-disc area visible; joint visibility means some solar
area visible while Earth's centre clears the terrain. Neither is an energy,
thermal, RF or landing-safety calculation.

`illumination_model="sun_center"` explicitly selects the historical centre-only
model. Existing snapshot artifacts remain unchanged. Solar-disc planning
requests, including default P1 requests, use the coordinate engine rather than
relabeling snapshot centre visibility as disk fraction. Legacy `/api/analyze`
and versioned snapshot endpoints retain their historical contract.

## Ephemeris and speed

`scripts/prepare_shared_ephemeris.py` downloads official NAIF kernels via HTTPS,
records source URLs/bytes/SHA-256, and verifies installed files. The runtime does
not download kernels or call a remote service for solar-disc calculations.

The provider uses `spkpos`, `MOON_ME`, `LT+S`, DE440 and its matching lunar frame
and orientation kernels, with the leap-second kernel for UTC-to-ET conversion.
Hourly float64 Sun/Earth vectors are stored in hash-checked monthly chunks with
both boundaries. They are shared across observers. Interpolation precedes
subtracting the actual observer vector (terrain elevation plus the separate
panel/antenna heights) and rotating into ENU. Earth parallax is retained.

Monthly generation is lazy; optional `--start`/`--end` prewarms tables. No
application mission-duration maximum is imposed. Dates must be supported by
the installed kernels; unsupported epochs raise `OUTSIDE_EPHEMERIS_COVERAGE`,
never clamp to another date. Missing installation returns
`EPHEMERIS_NOT_PREPARED`; integrity failures remain errors. Offline means no
network: local kernels may generate a previously uncached month.

Every request compares interpolation against exact SPICE at up to 25 epochs,
including deliberately non-hourly probes. The provisional angular check is
0.001 degrees. This is a sampled interpolation check, not a continuous error
bound. Release evidence independently compares native JPL observer tables on
both 1/5-minute grids. The runtime's 1/5-minute comparison resamples the shared
hourly table and is labeled accordingly; it is not presented as two independent
JPL acquisitions.

Horizon caching remains independent of dates/requirements. Bounded in-memory
visibility caches reuse physical series across threshold/contact changes.
UTC array conversion and JSON/CSV serialization avoid Python Timestamp boxing;
machine JSON caches use compact encoding. The frontend uses at most 800
duration-weighted display bins; full samples remain in backend results.

## Solar-disc numerical model and decision gates

64 vertical midpoint strips integrate visible disk area against the horizon at
each strip's bearing. The apparent Sun/Earth angular radii use topocentric
distances. Solid-Earth overlap is subtracted. Full-light/full-dark shortcuts
check a horizon neighbourhood enclosing the whole disk, not just its centre.
64/128-strip comparisons must differ by no more than 0.002 of disk area.

Missing evidence produces fractional lower/upper bounds, weighted by actual
interval duration; it is not converted to zero sunlight or full sunlight.
Numerical horizon/radius/time comparisons, frame checks, DEM seams and coverage
remain active. Sunlight thresholds use equivalent full-disc hours divided by
the actual mission duration. Method, evaluation and source identities separate
the new results from historical caches.

A violated hard requirement remains FAIL even when validation has warnings.
PASS still needs full validation or the conservative mission-path override.
The override checks the whole disk against padded profiles; partial disks stay
unknown in that override instead of inheriting centre-visible=100%. An
interpolation or quadrature validation failure cannot be bypassed by it.
Some long or threshold-adjacent cases therefore remain INDETERMINATE.

Limitations: sampled terrain/time, empirical numerical tolerances, angular-plane
strip approximation, no limb darkening or atmospheric eclipse dimming, and no
physical DEM uncertainty bound or global occluder certification. Increasing
precision is not evidence of independent physical accuracy.

## Sources and reproduction

- [NAIF SPKPOS](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/spkpos_c.html)
- [Official NAIF kernels](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/)
- [JPL Horizons observer conventions](https://ssd.jpl.nasa.gov/horizons/manual.html)
- Architecture/visualization reference: [BroBYW repository, reviewed revision ad699f0](https://github.com/BroBYW/CLPS-Lunar-Mission-Website/tree/ad699f0559c38bba522a5a92b62f2b99a351f7c2).
  Its derived ephemeris and horizon files are not scientific inputs to HOSA.

See [acceptance evidence](../validation/lunarsight/solar-disc-backend.md).
