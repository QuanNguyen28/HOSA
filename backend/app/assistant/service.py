from time import monotonic, perf_counter

from starlette.concurrency import run_in_threadpool

from .config import AssistantSettings
from .clarification import questions_for
from .engine import PlanningAdapter, digest
from .explanations import valid_plan, render
from .models import EvaluateRequest, EvaluateResponse, ExplainPlan, ParseRequest, ParseResponse, RequestPatch
from .prompts import PROMPT_VERSION, explain_messages, parse_messages
from .provider import AssistantError, JsonLLM
from .store import Draft, DraftStore


class AssistantService:
    def __init__(self, settings: AssistantSettings, llm: JsonLLM, drafts: DraftStore, engine=None):
        self.settings, self.llm, self.drafts = settings, llm, drafts
        self.engine = engine or PlanningAdapter()

    async def parse(self, request: ParseRequest) -> ParseResponse:
        caps = await run_in_threadpool(self.engine.capabilities)
        issue = self.engine.baseline_issue(request, caps)
        if issue:
            return ParseResponse(status="NEEDS_INPUT", issues=[issue], questions=questions_for(issue), llm_calls=0)
        reply = await self.llm.complete(RequestPatch, parse_messages(request, caps))
        try:
            spec = self.engine.normalize(request, reply.output, caps)
        except AssistantError as error:
            status = "UNSUPPORTED_REQUIREMENT" if error.code.startswith("UNSUPPORTED") else "NEEDS_INPUT"
            return ParseResponse(status=status, issues=[error.code], questions=questions_for(error.code, reply.output), patch=reply.output, llm_calls=1)
        spec_hash = digest(spec.model_dump())
        identifier = self.drafts.create(Draft(spec, spec_hash, monotonic()+self.settings.assistant_draft_ttl_seconds,
            reply.latency_ms, reply.model, parse_usage=reply.usage), self.settings.assistant_max_drafts)
        return ParseResponse(status="READY", issues=[], patch=reply.output, draft_id=identifier, spec_hash=spec_hash,
            baseline_hash=spec.baseline_hash, spec=spec, llm_calls=1)

    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:
        if not request.confirmed:
            raise AssistantError("CONFIRMATION_REQUIRED", 409)
        draft = self.drafts.get(request.draft_id)
        if request.spec_hash != draft.spec_hash:
            raise AssistantError("SPEC_CHANGED", 409)
        if digest(request.baseline.model_dump()) != draft.spec.baseline_hash:
            raise AssistantError("STALE_BASELINE", 409)
        caps = await run_in_threadpool(self.engine.capabilities)
        if caps["source_hash"] != draft.spec.source_hash:
            raise AssistantError("STALE_DATASET", 409)
        draft, claimed = self.drafts.claim(request.draft_id)
        if not claimed:
            return draft.result
        started = perf_counter()
        try:
            evidence = await run_in_threadpool(self.engine.evaluate, draft.spec, request.draft_id, draft.spec_hash)
        except AssistantError as error:
            self.drafts.fail(request.draft_id, error.code, error.status_code)
            raise
        except (OSError, ValueError) as error:
            self.drafts.fail(request.draft_id, "DATA_NOT_READY", 503)
            raise AssistantError("DATA_NOT_READY", 503) from error
        engine_ms = (perf_counter()-started)*1000
        plan, explain_usage = None, None
        explain_started = perf_counter()
        try:
            reply = await self.llm.complete(ExplainPlan, explain_messages(evidence))
            explain_usage = reply.usage
            if valid_plan(reply.output, evidence):
                plan = reply.output
        except AssistantError:
            pass  # Preserve science and render templates, never call a third time.
        text, fact_ids = render(evidence, plan)
        response = EvaluateResponse(evidence=evidence, explanation_mode="llm_plan" if plan else "template_fallback",
            explanation=text, explanation_fact_ids=fact_ids, llm_calls=2, model=draft.model,
            prompt_version=PROMPT_VERSION, token_usage={"parse": draft.parse_usage, "explain": explain_usage},
            timings_ms={"parse": draft.parse_ms, "engine": engine_ms, "explain": (perf_counter()-explain_started)*1000})
        self.drafts.finish(request.draft_id, response)
        return response
