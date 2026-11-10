# Availability as hard requirements; continuity as soft preferences

Effective policy: `availability-hard-continuity-soft-v1`, planning schema 2.0,
method `planning-services-2.0`, dataset v0.3.0. This decision supersedes the
continuity-based feasibility policy in the earlier proposal and planning notes.
The user authorized this policy change; the scenario remains PROVISIONAL.

Both `min_sunlit_fraction` and `min_earth_los_fraction` are required inputs.
`total_sun_hours` and `total_earth_los_hours` are their underlying measurements.
For mission duration D and minimum f, PASS requires L/D >= f, FAIL requires
U/D < f, otherwise the requirement is INDETERMINATE. Equality passes. Overall
feasibility uses only these two hard requirements. The demo UI starts at 80% for
each; these are editable examples and are not NASA-specified flight thresholds.

`max_darkness_hours` and `max_earth_blackout_hours` in `constraints` are nullable,
optional soft preferences. Their state and violation bounds are returned in
separate fields. Neither a soft FAIL nor soft INDETERMINATE blocks an otherwise
hard PASS. Longest joint visibility remains an additional descriptive/ranking
metric. A hard total shortfall is explained by aggregate bounds, not attributed
to one longest blocked event; the full Sun/Earth timeline is retained.

Compare/search filter on hard feasibility first. The default primary ranking is
total Earth LOS. For equal primary metric values, fewer failed soft preferences,
then fewer indeterminate soft preferences, break the tie; the existing site/date
tie-break follows. Rank ranges describe the selected metric only. Fallback
near-miss ordering uses hard shortfalls only and never enables application.

Sensitivity re-evaluates both hard minima on the exact selected site/window.
Soft-only changes are exposed as `soft_preferences_changed` without changing the
hard decision stability label. Missing comparison coverage stays NOT_EVALUATED.
Current independent 1-minute coverage is limited to the first supported 72 hours.

v0.3.0 is built from the immutable v0.2.0 interval products. Geometry, ephemerides,
site coordinates and coverage states are copied byte-for-byte. Earth total
bounds sum V for L and V or ? for U with clipped actual interval weights; they
are not inferred from the longest blackout. The builder records source/output
hashes in derivation.json. Historical v0.2.0 windows retain their original policy.

API/CLI clients must supply both minima; the backend does not invent a missing
hard requirement. Assistant baselines carry both; explicit new user input
overrides the baseline values; planning_context carries rank/search only, so hard minima have one authoritative home. The assistant
cannot explain a hard FAIL using a soft-only violation. JSON/CSV, capabilities,
CLI and UI expose the distinction consistently.
