# LunarSight integrated MVP

React/Three.js frontend connected to the shared FastAPI backend. The original `feature/lunarsight-frontend` product shell stays in `src/figma/App.tsx`: header, Site/All sites sidebar, Moon/Pole/Ground viewer, timeline, compare cards, date grid and Ask dock. Its data flows now call real backend APIs; the synthetic horizon/ephemeris/metric generators and heuristic chat have been removed.

## Run

Node **22.12+**, npm **10.5.1+**. An `.nvmrc` is included.

```bash
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Start the backend separately at port 8000. For another backend:

```bash
LUNARSIGHT_BACKEND_URL=http://127.0.0.1:8001 npm run dev -- --port 5174
```

The same proxy setting works with `npm run preview` after `npm run build`.

## Connected flows

- **Explore:** API catalog or exact coordinates; queued point analysis with progress, validated metric bounds, contact windows, native timeline and JSON download.
- **Compare:** `/api/planning/compare`, `data_source=coordinate`; common mission requirements and hardware, with backend PASS/FAIL/INDETERMINATE. JSON/CSV exports come from the persisted backend result.
- **Best dates:** `/api/planning/windows/search`; exclusive end for candidate starts, configurable step, up to 128 evaluations. Every candidate is a mission of 1–72 whole hours.
- **Assistant:** actual `/api/assistant/parse` → review → `/api/assistant/evaluate`. It currently supports the Site01/Site04 snapshot scenario, fixed 72 hours and 1/2 m hardware. It retains evaluated context and selected sites between turns and tabs. It displays the disabled state when the backend has no assistant configured. No client-side key or simulated chat answer is used.

Coordinates and mission changes hide stale results. Original named-site coordinates are preserved, and Site01/Site04 use the exact API catalog coordinates; the two sets are not aliased. The DEM viewer similarly rejects stale terrain responses when selecting another point. The 3D Sun lighting is a labelled visual preview; all displayed mission metrics/decisions are from the backend.

## First live check

Default mission (viewer initially selects Connecting ridge; A/B are available under All sites): 24 November 2026 UTC, 72 hours, panel/antenna 20 m, minimum sunlight 80%, at least one 30-minute contact after 5-minute setup, completing by minute 120. These are explicit example settings, not general mission standards.

1. Open **All sites**, select **Example A**, then Analyze: the documented NASA/JPL case yields PASS.
2. Analyze **Example B**: yields FAIL. Changing points clears the previous result.
3. Compare both: one PASS, one FAIL. Search the initial 15-minute range: evaluate two candidates and return the PASS.
4. Download JSON/CSV and compare their result identifiers and metric values.

Real DEMs must be installed (`scripts/prepare_point_data.py`, about 0.5 GB). First-time JPL requests require internet and may take several minutes. Cache-only mode requires the exact observer, hardware and date range; missing evidence stays unknown.

## Verify

```bash
npm test
npm run typecheck
npm run build
```

From the repository root, test the running API without an LLM:

```bash
backend/.venv/bin/python scripts/verify_mvp_api.py --base-url http://127.0.0.1:8000
```

Use `--offline` only when the matching JPL cache already exists. See `docs/demo/fe-be-mvp.md` for branch integration and browser acceptance evidence.
