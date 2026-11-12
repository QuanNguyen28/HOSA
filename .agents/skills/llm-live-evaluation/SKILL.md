---
name: llm-live-evaluation
description: Run or review strict live evaluations for HOSA LLM providers, including provider smoke, grounded golden cases, multi-turn chat, and failover evidence.
---

# LLM Live Evaluation

Use `scripts/assistant_eval.py` and the assistant fixtures as the starting point; inspect their current behavior before relying on them. Run NVIDIA and Gemini independently with failover disabled for strict provider scores. Use the HTTP API only for failover cases and confirm the trace names the actual serving provider.

## Evaluation workflow

1. Record the clean working tree or source hash, Python/Node versions, dependency lock state, test command and dataset manifest version. Verify provider configuration without printing key values.
2. Preflight each provider separately: auth/model, Vietnamese response, schema-valid JSON, streaming final event, reasoning settings, usage and one knowledge response grounded in a real project source.
3. For mission behavior, obtain expected decision, metrics, candidate IDs and provenance by calling the deterministic engine directly with the frozen request and data. Never author a model-expected scientific result by hand.
4. Evaluate knowledge facts against required evidence and forbidden claims rather than exact prose. Test English, Vietnamese, unaccented Vietnamese, ambiguity, long history, corrections, cancellation, reconnect, stale apply state, injection, missing data, PASS, FAIL and INDETERMINATE.
5. Test failover by injecting the primary transport error and verifying a real secondary inference. Do not intentionally consume quota to cause rate limiting. Do not count failover as a primary-provider strict pass.
6. Preserve sanitized case/run IDs, UTC, requested and actual provider/model, upstream request ID, prompt/schema/source version, finish reason, usage, queue/provider latency, retries, repair, failover, outcome and error code.
7. Report passed, failed, blocked and not-run separately. Missing keys, provider outage, quota exhaustion, environmental dependency gaps, or truncated outputs are not passing skips. Redact all credentials and internal reasoning from artifacts.

## Acceptance

Keep strict provider scores separate. Critical routing, citation, source, candidate, validation and apply cases must all pass. No response may upgrade INDETERMINATE to PASS or mutate an applied plan without the explicit apply route. Reproduce each defect, fix it, add a deterministic regression, and rerun the affected group before updating the report. A smoke response or green unit suite alone does not prove live acceptance.
