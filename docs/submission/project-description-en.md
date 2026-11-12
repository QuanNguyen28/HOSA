# HOSA — submission copy

Status: **submission-ready draft; team/event/link fields still required**.

## One-line pitch

HOSA turns NASA lunar terrain and JPL ephemerides into an explainable,
reproducible comparison of illumination and geometric Earth visibility at two
candidate locations near the Moon's south pole.

## Project description

Choosing when and where to operate near the lunar south pole is difficult because
low Sun and Earth elevation angles allow nearby terrain to create long periods of
shadow or blocked line of sight. A static map or a long-term percentage does not
show which event disqualifies a specific 72-hour activity window.

HOSA is an educational web prototype that compares two supported lunar
south-pole observation points across 1,344 gridded start times. It combines NASA
LOLA/PGDA digital elevation models with topocentric Sun-center and Earth-center
angles from JPL Horizons. For each exact 15-minute start, the same deterministic
analysis evaluates a fixed 72-hour activity at five-minute resolution.

Users can explore a three-dimensional Moon, inspect local terrain and compare the
two candidate sites under shared constraints. The result is not only pass or fail:
the interface identifies the decisive blocked interval and links it to the target's
azimuth, elevation, terrain-horizon angle and clearance. A three-state model
(`PASS`, `FAIL`, `INDETERMINATE`) preserves uncertainty and coverage gaps instead
of silently treating unknown samples as visible or blocked. JSON and CSV exports
retain the request, data version and method version so another person can reproduce
the result.

The current MVP intentionally keeps its scientific claim narrow. Sun visibility
is a geometric Sun-center test, not a power or thermal model. Earth visibility is
geometric line of sight to Earth's center, not a communications link budget. The
prototype supports two precomputed sites and one provisional demonstration
scenario; it is not a landing-safety certification tool.

## What makes it useful

- **Explainable decisions:** every failed constraint points to a concrete event
  and its terrain evidence.
- **Fair comparison:** both sites use the same epoch, activity duration, device
  heights, time grid and decision rules.
- **Explicit uncertainty:** incomplete coverage produces an indeterminate state,
  while numerical-sensitivity flags remain separate from the decision.
- **Reproducibility:** versioned inputs, provenance receipts, configuration,
  automated tests and export metadata support independent reruns.
- **Accessible learning:** a 3D exploration view connects lunar geography with the
  timeline and horizon profile used in the analysis.

## Technical approach

The data pipeline validates NASA LOLA rasters, pixel registration, reference frame
and region membership before computing local east-north-up terrain horizons. JPL
Horizons ephemerides are cached with request receipts and parsed into normalized UTC
time series. Visibility is determined by the signed clearance between target
elevation and the interpolated terrain horizon at the matching azimuth. Consecutive
states are converted into half-open intervals and aggregated into 72-hour metrics,
including longest darkness and longest Earth-LOS blackout. The FastAPI service
exposes scenario, profile, analysis and reproducible-export endpoints; the React
and Three.js client provides the Explore and Compare workspaces.

The implementation includes synthetic geometry tests, temporal edge cases,
two-resolution horizon comparisons and independent one-minute ephemeris checks.
In the documented sensitivity cases, the 72-hour decision remained unchanged;
the interface still reports angular sensitivity where the maximum local horizon
difference exceeds the provisional tolerance.

## Data and credits

- Lunar terrain: NASA Planetary Geology, Geophysics and Geochemistry Laboratory
  (PGDA), Lunar Orbiter Laser Altimeter (LOLA) products.
- Sun and Earth ephemerides: NASA/JPL Horizons System.
- Global visualization textures: NASA LRO/LOLA derivatives with local provenance
  recorded under `frontend/public/assets/nasa/`.
- Challenge context: NASA International Space Apps Challenge 2026, Lunar Landing
  Site Navigator.

NASA and JPL data are used for an independent educational prototype. The project
does not imply NASA or JPL endorsement.

## Required fields before submission

- Team name: `REQUIRED`
- Team members and roles: `REQUIRED`
- Local/Universal Event: `REQUIRED`
- Repository URL and public-access result: `REQUIRED`
- Public demo URL and public-access result: `REQUIRED`
- Video URL, duration and current-rule compliance: `REQUIRED`
- Thumbnail and screenshots with credits: `REQUIRED`
- AI-use disclosure required by the current event form: `REQUIRED`
- Open-source license approved by the rights owner: `REQUIRED`

