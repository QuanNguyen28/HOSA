# Backend and LLM release

Base: `feat/fix-compute-backend`, commit `1e5d598bf93ad075376680645a3d44f19328322d`.

This branch adds native providers, grounded session chat, result interpretation, UTF-8 terminal tools and regression tests. Frontend files and scientific source datasets remain at the base revision. The only scientific-pipeline changes are cooperative cancellation checkpoints and bounded retries of transient Windows atomic-file replacement errors; formulas, thresholds and validation gates are unchanged.

## Local setup

From the repository root, with Python 3.11 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[test]'
Copy-Item .env.example .env
```

In the ignored `.env`, set `ASSISTANT_ENABLED=true` and configure `NVIDIA_API_KEY` and, for failover, `GEMINI_API_KEY`. Default models are GLM 5.3 Flash and Gemini 3.1 Flash Lite. For a strict DeepSeek experiment, set `NVIDIA_MODEL=deepseek-ai/deepseek-v4.1-flash` and `ASSISTANT_FAILOVER_ENABLED=false`. DeepSeek's observed multi-minute latency is documented in [verification status](LLM_IMPLEMENTATION_STATUS.md).

The committed snapshot supports the original comparison scenario. Arbitrary-coordinate analysis requires verified DEM assets and observer/time-specific Horizons evidence. Set `LUNARSIGHT_RAW_DATASET_PATH` to an immutable delivery for metadata indexing or verified imports; do not commit the delivery or assume catalog entries are validated mission results.

The full science test suite also needs the verified Site01/Site04 and regional DEM assets. Import them from the delivery without changing the originals:

```powershell
.\.venv\Scripts\python.exe scripts/import_nasa_delivery.py --delivery-path 'C:\path\to\delivery' --datasets Site01 Site04 dem80 dem240
```

Start API manually from `backend`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then, from the repository root, run the shared HTTP terminal client:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/assistant_chat.py --new
```

Alternatively, on Windows the UTF-8 launcher starts a hidden API if none is listening:

```powershell
pwsh -NoExit -File scripts/open_assistant_terminal.ps1 -New
```

`-Model deepseek-ai/deepseek-v4.1-flash -Strict` is an explicit NIM experiment. An already running API must match those overrides; the launcher refuses a mismatch rather than silently replacing an active server. Logs and SQLite state are in ignored `data/cache/assistant`. Terminal commands: `/help`, `/new`, `/unicode`, `/result`, `/apply <candidate_id>`, `/quit`; Ctrl+C during a run requests cancellation.

## Validation and evaluation

Offline checks use real committed snapshots where applicable, with synthetic transport/data failures for recovery cases. Run:

```powershell
New-Item -ItemType Directory -Force data/cache/assistant | Out-Null
$testTemp = Join-Path (Get-Location).Path ('data/cache/assistant/pytest-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest -q --basetemp $testTemp
```

Use a fresh basetemp path for each run. Real API calls are explicitly opt-in and write sanitized reports to ignored cache:

```powershell
.\.venv\Scripts\python.exe scripts/provider_preflight.py --provider nvidia
.\.venv\Scripts\python.exe scripts/assistant_eval.py --live --provider nvidia
.\.venv\Scripts\python.exe scripts/assistant_eval.py --live --provider gemini
.\.venv\Scripts\python.exe scripts/assistant_failover_eval.py
```

Strict evaluation disables failover for the chosen provider. Failover evaluation injects a NIM 429 and requires a real Gemini inference. Never count mock/template output, a catalog-only response or a different provider as a strict model pass.

Release-checkout verification on 2026-11-12: **283 backend tests passed**, with one existing Starlette/httpx deprecation warning, using Python 3.12.7, the committed snapshots and locally available verified DEM assets. All v0.3.0 derivation input/output checksums matched. Four new project skills passed the skill validator, the PowerShell launcher parsed without errors, and the UTF-8 terminal subprocess round-trip passed. No new live provider calls were required for packaging this branch.

The broader live acceptance gates in the original plan remain incomplete; this release does not claim low latency or unrestricted external provider availability. The publication SHA is provided at handoff.
