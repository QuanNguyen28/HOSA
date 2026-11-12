# FE–BE MVP acceptance

Date: 2026-11-12. Branch: `feat/merge-fe-be`.

## Integration under test

- Backend source: `feat/fix-compute-backend` at `1e5d598`, plus review fixes committed as `06920a2`.
- Frontend source: `feature/lunarsight-frontend` at `23ab188`; source merge: `8eb0684`.
- Application entry: original `frontend/src/figma/App.tsx`, preserving the frontend branch product shell, font/color tokens, Moon/Pole/Ground controls, Site/All sites panel, timeline, comparison cards, date grid and Ask dock. Backend adapters replace mock metric/chat calls. Original named-site coordinates are not aliased to Site01/Site04.
- Real local FastAPI on port 8001, Vite dev on 5174, production preview on 4174. Chrome through the Playwright CLI and the integrated browser for final production acceptance. No mocked science responses.
- Python virtual environment and Node 22.23.5. Dependencies include Shapely 2.1+ required by the merged catalog tools.

## Automated verification

`make verify`: backend pytest, frontend Vitest, TypeScript typecheck and production build. Backend: **269 passed**, one dependency warning (71.91 s). Frontend after original-shell integration: **28 passed** across four files. TypeScript and Node 22 production build passed. Logs: `/tmp/hosa-mvp-final-verify.log`, `/tmp/hosa-mvp-figma-final-build.log`.

Live API verification:

```bash
backend/.venv/bin/python scripts/verify_mvp_api.py \
  --base-url http://127.0.0.1:8001 --offline
```

Passed: direct point decisions/validation match coordinate compare/search, candidate identity is stable, saved JSON export equals its API response, CSV contains both candidates. This check uses real NASA terrain and exact cached JPL data; it makes no LLM call.

## Direct browser checks

Shared mission: 2026-11-24T00:00:00Z, 72 hours, panel/antenna 20 m, sunlight fraction 0.8, contact 30 minutes + setup 5 minutes, one required window, first-contact completion deadline 120 minutes. Darkness 12 hours / blackout 6 hours are secondary preferences.

| Check | Observed result |
|---|---|
| Analyze Example A: (-88.80771296769387, 123.81313283430084) | PASS; sunlight/Earth LOS 72 h; dark/blackout 0 h; validation passed |
| Analyze Example B: (-87, 180) | FAIL; sunlight/Earth LOS 0 h; dark/blackout 72 h; validation passed |
| Change point or mission date | Previous metrics disappear before the new calculation; no stale result |
| Compare A and B | FEASIBLE; two evaluated, one PASS, one FAIL, zero INDETERMINATE |
| Search [2026-11-24 00:00, 00:15) UTC at 15-minute step | Two evaluated, one PASS returned; same candidate ID as Compare |
| JSON and CSV download buttons | Files downloaded; direct/compare/search metrics, identifiers and CSV rows checked against each other |
| Enter 73 mission hours | Analysis disabled with validation message |
| Search beyond 128 candidate evaluations | Search disabled with validation message |
| Cache-only request for 2028-01-01 | Actual failed job reports HORIZONS_CACHE_MISS; no stale or invented metrics |
| Surface camera at Example A | Actual COVERED DEM window, 80 m native resolution, 257 × 257 grid; terrain mesh rendered |
| Mobile 390 × 844 | No horizontal page overflow; final original-shell dock check: viewport 390, document width 375 (scrollbar) |
| Browser console | No application errors in the isolated acceptance session; WebGL ReadPixels performance warnings observed |

Direct real-model Assistant check:

1. Requested arrival 2026-11-17T00:00:00Z, Site04_P1 only, unchanged hardware. Parse returned READY with the requested site/date.
2. Confirmed evaluation returned Site04 INDETERMINATE / INSUFFICIENT_DATA, apply_allowed=false. Explanation used the backend's `template_fallback`; this is not evidence of a successful model-generated explanation.
3. Switched tabs and returned. Site04/date and conversation remained.
4. Requested minimum sunlight 90%, preserving current point/date/hardware. The next parse retained Site04/date and received the evaluated conversation history. Cancelled this draft without evaluating it.

Final original-shell checks also passed: Example A PASS / B FAIL with stale-result clearing; production Compare and Best dates returned the same decisions and result IDs as the earlier API checks. Production Compare JSON/CSV downloads were read from the browser download folder and verified for matching candidate IDs and both decisions. A real keyboard change of the datetime input confirmed the >128 evaluation guard (1536 evaluations, Search disabled). Native browser automation's datetime fill alone did not emit React's change event; keyboard interaction was used to verify actual behavior. Cache-only 2028-02-01 in the original shell also returned HORIZONS_CACHE_MISS with no displayed metric.

The original-shell production Assistant also completed the Site04/date change, retained context across the full page and Ask dock, and parsed the 90% sunlight follow-up with Site04/date unchanged; the follow-up draft was cancelled. Direct testing found the old floating Close button overlapping Send in the dock; Close was moved into the dock header. The final frontend check after that fix passed all 28 tests, typecheck and build (14.79 s). Final assets: `index-Cunb9lza.js`, `index-CbmCJ1ql.css`. Reloaded that build and verified Send in the dock returned a READY Site04 draft (then cancelled); Analyze A again returned PASS, its downloaded JSON matched Compare metrics/validation/result ID, the Ground viewer rendered dem80 / 80 m / 257² vertices, and the production console contained zero errors. The temporary mobile viewport was reset; desktop was restored to 1280 px.

Local artifacts (gitignored, retained in this workspace):

- `output/playwright/figma-production-compare.json`, `figma-production-compare.csv`, `figma-production-point-a.json`
- `/tmp/hosa-mvp-final-api-smoke.json`
- `output/playwright/figma-restored-initial.png` (restored original frontend shell)
- `output/playwright/mvp-explore-real.png` (earlier API integration verification before restoring the original shell)
- `output/playwright/mvp-compare.png`
- `output/playwright/mvp-mobile.png`
- `output/playwright/example-b.json`, `compare.json`, `compare.csv`, `search.json`
- `/tmp/hosa-mvp-final-verify.log`

## Scope of acceptance

This is local MVP integration acceptance, not physical certification. Results remain sampled, geometric, PROVISIONAL Sun/Earth-centre visibility. No RF link budget, power, thermal or landing-safety certification is implied. Missing evidence or failed numerical gates remains INDETERMINATE.

Assistant currently uses the existing Site01/Site04 snapshot contract (72 hours, panel/antenna 1/2 m), explicitly labelled in the UI. It does not inherit the coordinate/contact form. Coordinate Explore/Compare/Best dates share the newer backend mission contract. Chat is retained in browser memory across tabs; page refresh or New conversation starts a new conversation.

Raw NASA data, JPL caches, private environment files and model keys are not part of the commit. New dates can require network access; a clean checkout must prepare DEM data and populate the relevant cache or allow JPL access.
