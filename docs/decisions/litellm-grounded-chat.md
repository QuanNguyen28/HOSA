# LiteLLM proxy and contextual answers

The local UI can use an OpenAI-compatible LiteLLM gateway with `ASSISTANT_PROVIDER=openai`. This is a transport name, not a claim that inference is served by OpenAI. The configured gateway exposes the alias `gemini/gemini-3.8-flash`; the `/models` response and live completions were checked independently. The physical model behind a gateway alias cannot be independently certified by the application.

## Local configuration

Keep the key in the ignored worktree `.env`:

```dotenv
ASSISTANT_ENABLED=true
ASSISTANT_PROVIDER=openai
ASSISTANT_STREAMING=true
ASSISTANT_FAILOVER_ENABLED=false
ASSISTANT_NATURAL_EXPLANATIONS=true
ASSISTANT_ANSWER_REVIEW=true
LLM_PROXY_BASE_URL=https://ai-proxy.honglinheducation.vn/v1
LLM_PROXY_MODEL=gemini/gemini-3.8-flash
LLM_PROXY_API_KEY=<local-secret>
LLM_PROXY_RESPONSE_FORMAT=json_schema
```

Use `LLM_PROXY_*` rather than `OPENAI_*`: a host-level `OPENAI_API_KEY` can otherwise override the worktree credential. No key is sent to the frontend or added to prompts/reports. The base URL must be HTTPS with no embedded credentials, query or fragment. Requests use Bearer authentication, as described in [LiteLLM virtual-key authentication](https://docs.litellm.ai/docs/proxy/api_key_auth).

The adapter sends portable OpenAI-compatible messages, response format, model and stream fields. It does not send OpenRouter routing parameters, NVIDIA template parameters or Google-native generation fields. Clients are pooled for the application lifespan. Connect timeout is bounded; reads and generation have no application deadline. An optional verified per-request budget can be set with `LLM_PROXY_MAX_OUTPUT_TOKENS`. The gateway's actual default/context/output limits remain unverified; omitting this value does not mean unlimited generation upstream.

Malformed/truncated structured output permits one repair, transient connection/5xx failure one retry, at most three attempts total. Authentication, invalid request, missing model and rate-limit errors remain explicit; the proxy does not silently switch to another account/provider. Trace records include requested/returned model, stage, completion/header ID when supplied, finish reason, usage, prompt/schema hashes, latency and sanitized errors. Private reasoning and authorization headers are excluded.

## Why answer behavior changed

General chat previously searched raw user words directly against a mostly English index. This missed related concepts in Vietnamese and short follow-ups. The HTTP session/run flow now asks the same configured LLM for up to three focused retrieval queries using conversation context. The backend searches only its local index, interleaves results, and includes a bounded set of current project-orientation passages with real source IDs/hashes. Generated retrieval text has no file, URL or shell access. This adds an inference stage and its latency is included in the report.

The answer policy asks for a direct conclusion with relevant causes and planning implications, adaptive paragraph length and few numbers. It does not prescribe a fixed response or a command-word dictionary. The current data/interpretation guides explain the distinction between total availability and continuity, hard requirements and soft preferences, nominal and validated decisions, imagery and scientific geometry, and geometric opportunities versus physical power/radio performance.

With `ASSISTANT_ANSWER_REVIEW=true`, a separate model completion edits the draft against the same source/evidence packet before display. This addresses overconfident claims and uncertain terminology observed during manual live review. It may remove or qualify unsupported prose, but cannot change routing/query or engine decisions. Its output goes through source/claim/contract validation again. It is not a canned answer or an infallible factual verifier. This additional model call is included in latency and usage; disable the setting explicitly only if accepting the quality/latency trade-off.

Mission planning's `/parse` and confirmation behavior remain intact. `/evaluate` previously requested only a reason-code plan and rendered fixed metric sentences. It now requests `NaturalExplainPlan`: generated prose plus candidate-specific reason/fact references and exact final decisions. Candidate identity, fact membership, status and decision remain backend-validated. The narrative receives qualitative evidence by default; explicit numeric questions retain numeric facts. It is not allowed to turn a passed threshold into full continuous visibility. Numerical result cards still come from the engine. An invalid explanation is marked `llm_failed`; a visibly labelled computed-result summary is never counted as LLM success. `ASSISTANT_NATURAL_EXPLANATIONS=false` retains the old compatibility renderer.

JSON schemas keep free-form tool argument objects open rather than stripping their permitted properties. The backend then validates typed mission arguments through the existing Pydantic/business contracts. Fixed-contract objects still reject unexpected fields.

## Reproducing checks

Use the project's installed Python environment:

```powershell
python scripts/provider_preflight.py --provider openai
python scripts/assistant_eval.py --live --provider openai --cases tests/fixtures/assistant/proxy_reasoning_cases.json
python scripts/planning_narrative_eval.py --live --base-url http://127.0.0.1:5179
python -m pytest tests/assistant tests/planning tests/test_assistant_reliable.py tests/test_chat_interpretation.py tests/test_proxy_llm.py tests/test_provider_preflight.py tests/test_mission_unification.py tests/test_moontrek_imagery.py -q
```

`--live` makes actual inference requests and may incur gateway charges. Reports are written under ignored `data/cache/assistant/`. The live suite includes open questions, Vietnamese with/without accents, English, language switching, multi-turn follow-ups, injection/missing-data claims, compare and best-date search. Compare/search use direct engine outputs as the scientific oracle. The separate planning script verifies the exact UI parse/review/evaluate transport and full evidence against the deterministic engine.

Automated routing/schema/reference/oracle checks are separate from reviewing naturalness and factual entailment. A valid source ID does not itself prove that the prose follows from the source. Read the saved answers, including all critical scientific explanations. This focused acceptance suite does not replace the earlier proposed 160-case-per-provider evaluation or an hour-long soak test.
