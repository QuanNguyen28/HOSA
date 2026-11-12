# Application acceptance

Verification date: 2026-11-09 Asia/Ho_Chi_Minh.

This report records the application-layer checks for the versioned HOSA v0.2.0 science products. It does not replace the pipeline scientific validation report.

## Automated gates

| Gate | Result | Evidence |
|---|---|---|
| Python unit and integration tests | PASS | 36 tests passed in 0.92 s |
| Frontend TypeScript check | PASS | `tsc --noEmit` completed without errors |
| Frontend production build | PASS | Vite built 2,149 modules in 2.81 s |
| Exact start grid | PASS | integer range `[0,1344)`; no nearest-window substitution |
| Immutable scenario fields | PASS | `D_hours` and device-height overrides return HTTP 400 `UNSUPPORTED_CONFIG` |
| Two-site comparison | PASS | Site01 and Site04 evaluated from the same start index, duration and thresholds |
| Event explanation | PASS | failed constraint links to a blocked interval and worst clearance sample |
| Reproducible export | PASS | deterministic result ID; JSON and two-row CSV retain configuration and versions |
| Site04 temporal sensitivity | PASS | independent JPL 1-minute case retained the FAIL decision; maximum duration and event shift were 2 minutes |
| Site04 azimuth sensitivity | PASS with flag | 0.25/0.125-degree comparison changed 0 decisions; maximum horizon difference is reported as angular-sensitive |

## Performance gate

Five warm local requests through the Vite proxy for two-site analysis completed in 0.039-0.056 s. A two-site full-grid summary over 2,688 candidate starts completed in 0.050 s. Both are below the proposal target of two seconds on the demo machine.

## Browser verification

The Chrome demo at 127.0.0.1:5173 was inspected at 80% browser zoom. The Compare workspace visibly showed:

- scenario controls and exact 15-minute start index;
- Site01 and Site04 decisions, metric bounds and 72-hour event lanes;
- decisive Earth-blockage event with time, duration and worst clearance;
- 0.25-degree terrain horizon profile with the event marker;
- visible per-site numerical-sensitivity label;
- JSON and CSV export actions.

Changing the maximum Earth LOS outage from 6 h to 72 h changed both site decisions from FAIL to PASS, matching the backend rules.

## Remaining acceptance boundaries

- The scenario status remains PROVISIONAL because G0 mission-owner approval of epoch and thresholds is not recorded.
- User-task testing with 3-5 participants and the final submission video require real participants and the event submission format.
- Arbitrary-point terrain meshes are display and terrain-inspection products; arbitrary-point Sun/Earth mission analysis is outside the approved two-site MVP.
