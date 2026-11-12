# Backend and LLM verification status

Updated 2026-11-12. This branch contains backend, terminal, tests and supporting documentation; frontend behavior is inherited from the base branch. See [setup and release scope](BE_LLM_RELEASE.md).

## Implemented

- Native NVIDIA NIM and Gemini streaming transports, schema validation, sanitized traces, usage/model identity, retry/repair and explicit NIM-to-Gemini failover. Configuration/authentication failures are not hidden by fallback.
- Default NIM model `z-ai/glm-5.3-flash` with low reasoning effort and `clear_thinking=true`; Gemini `gemini-3.1-flash-lite` with minimal thinking. The unavailable original `z-ai/glm-5.3` was replaced with Flash with the project owner's approval.
- Optional `deepseek-ai/deepseek-v4.1-flash` uses its own thinking-off request fields, not GLM template parameters. Model selection comes from configuration; the terminal launcher respects it unless explicitly given `-Model`.
- SQLite WAL sessions, run events/SSE replay, cancellation, restart recovery and guarded explicit application of a PASS candidate. Existing mission, compare/search, contact and validation engines own science and decisions.
- Source-addressable project/data-metadata retrieval, metric meanings and result evidence. Test fixtures and environment configuration are excluded from knowledge retrieval. Explanations preserve final versus nominal decisions, hard versus soft checks and candidate identity.
- Qualitative explanation context by default, with numerical evidence available for explicit numeric/time/table questions. There is no answer word cap and no truncation of prose. Terminal `/result` displays detailed numerical output on demand; `/unicode` tests local keyboard/output without inference.

## Evidence and limits

Real preflight, structured streaming and strict chat calls were made with GLM Flash, Gemini and DeepSeek. Earlier independent GLM/Gemini ten-turn conversations passed; those are small samples rather than a complete acceptance benchmark. Some early explanation evaluations failed routing or the now-withdrawn short-answer criterion; later routing was corrected and word limits removed at the user's request. Do not treat removing a word-count criterion as proof of semantic quality.

A subsequent manual DeepSeek comparison completed through the session API with the expected model and no retries. Its two calls took approximately 199 and 331 seconds (about 8 minutes 50 seconds total), with roughly 12,000 input tokens per call. NIM latency and heavy context remain material limitations. Transport streaming currently collects the final JSON before returning answer text; progress events are not a live token display.

The application has no generation/read/total deadline, but retains a bounded connection timeout. Provider context/output limits, quotas, disconnections and cancellation still apply. This configuration can wait a long time on an upstream response; it is not a promise of failure-free service or low latency.

Structured evidence references and states are checked. This does not prove every free-prose sentence is correct or useful; content quality still needs human review. The 160-case corpus/provider, 12 independent long conversations/provider, critical-case repeats, complete live science matrix and 60-minute soak are not completed acceptance gates.

Final release validation and the exact base commit are recorded in [BE_LLM_RELEASE.md](BE_LLM_RELEASE.md). Credentials and local session/live-response caches are not committed.
