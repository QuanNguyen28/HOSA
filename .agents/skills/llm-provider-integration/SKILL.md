---
name: llm-provider-integration
description: Integrate or diagnose LunarSight's NVIDIA NIM GLM-5.3-Flash, optional DeepSeek-V4.1-Flash and Gemini 3.1 Flash-Lite adapters, including structured output, streaming, provider recovery, and safe traces.
---

# LLM Provider Integration

The shared provider contract lives in `backend/app/assistant/provider.py`; settings live in `config.py`, routes in `router.py`, and client lifecycle in `backend/app/main.py`. Keep API keys in ignored `.env` or environment variables. Never place credentials in source, prompts, fixtures, URLs, shell output, or reports.

## Provider rules

- NVIDIA NIM is the default at `https://integrate.api.nvidia.com/v1/chat/completions`, currently using `z-ai/glm-5.3-flash` because the configured account does not expose `z-ai/glm-5.3`. Use low reasoning effort and parse only final content; GLM-5.3-Flash reasoning cannot be disabled, so never claim that it is off.
- Gemini Developer API uses the stable `gemini-3.1-flash-lite` model and native `x-goog-api-key` authentication. Keep Gemini-specific generation and schema fields out of NIM requests and NIM-specific fields out of Gemini requests.
- Optional NIM `deepseek-ai/deepseek-v4.1-flash` uses `reasoning_effort=none` and `chat_template_kwargs.thinking=false`; do not send GLM-specific template fields. Keep it opt-in, and report observed latency separately from correctness.
- Keep structured responses behind the shared Pydantic contract. Provider success requires a complete final response, valid schema, usage/model/request metadata where available, and passing business validation.
- Bound connection establishment; leave response reads and generation unbounded by an application deadline. Derive generation budgets from verified model limits and remaining context. Provider quotas and context limits still apply.
- Preserve one retry for transient connection/5xx errors, one repair for malformed or truncated structured output, immediate NIM-to-Gemini failover for 429, and no failover that hides invalid credentials, unknown models, or malformed requests. Make provider choice sticky for the rest of a run.
- Apply the process-wide NIM cooldown and one half-open recovery probe. Keep per-provider concurrency bounded and HTTP clients pooled for the application lifespan.
- Keep trace records sanitized: provider, requested/returned model, stage, request ID, finish reason, UTC timestamp, latency, usage, attempt, and safe error code. Never record authorization headers or private reasoning.

## Verification

Use deterministic transport tests for every request shape, schema, SSE completion, UTF-8 chunking, finish reason, provider error, retry, repair, cooldown and concurrency path. Run provider preflight independently with the live-evaluation skill. Never count mock, cache, template, or fallback-served results as a successful strict-provider run. Disable failover for strict evaluation. If current official endpoint documentation is unclear, check NVIDIA's NIM reference or Google's Gemini API reference before choosing a field or limit.
