import asyncio
import json

from app.assistant.models import EvaluateRequest, NaturalExplainPlan
from app.assistant.provider import Completion
from app.assistant.explanations import valid_plan
from conftest import FixtureLLM


class NaturalLLM(FixtureLLM):
    def __init__(self, wrong=False):
        super().__init__()
        self.wrong = wrong
    async def complete(self, contract, messages):
        if contract is not NaturalExplainPlan:
            return await super().complete(contract, messages)
        payload = json.loads(messages[-1]["content"])
        if "draft_to_review" in payload:
            return Completion(NaturalExplainPlan.model_validate(payload["draft_to_review"]),"test-editor",1,{})
        answer = "Hai phương án cần được đánh giá theo đúng yêu cầu liên lạc; tổng thời gian khả kiến chưa đủ để suy ra một phiên liên tục."
        blocks = [{"candidate_id":c["candidate_id"],"site_id":c["site_id"],
            "decision":"PASS" if self.wrong and c["decision"] != "PASS" else "FAIL" if self.wrong else c["decision"],
            **c["allowed_reasons"][0]} for c in payload["candidates"]]
        for b in blocks:
            b.pop("bounds_hours",None); b.pop("limit_hours",None)
        plan = NaturalExplainPlan(run_id=payload["run_id"], spec_hash=payload["spec_hash"],
            lead_code=payload["status"], blocks=blocks, answer=answer)
        return Completion(plan,"test-natural",1,{})


def test_planning_returns_model_prose_without_rendering_a_fixed_metric_list(service, request_payload):
    from app.assistant.models import ParseRequest
    service.settings = service.settings.model_copy(update={"assistant_natural_explanations":True})
    service.llm = NaturalLLM()
    request = ParseRequest.model_validate(request_payload)
    parsed = asyncio.run(service.parse(request))
    response = asyncio.run(service.evaluate(EvaluateRequest(draft_id=parsed.draft_id,spec_hash=parsed.spec_hash,
        baseline=request.baseline, confirmed=True)))
    assert response.explanation_mode == "llm_plan"
    assert len(response.explanation) == 1 and response.explanation[0].startswith("Hai phương án")
    assert all(key in response.evidence.facts for key in response.explanation_fact_ids)
    assert service.drafts.get(parsed.draft_id).user_text == request.text


def test_natural_plan_cannot_change_candidate_decisions(service, request_payload):
    from app.assistant.models import ParseRequest
    service.settings = service.settings.model_copy(update={"assistant_natural_explanations":True})
    service.llm = NaturalLLM(wrong=True)
    request = ParseRequest.model_validate(request_payload)
    parsed = asyncio.run(service.parse(request))
    response = asyncio.run(service.evaluate(EvaluateRequest(draft_id=parsed.draft_id,spec_hash=parsed.spec_hash,
        baseline=request.baseline, confirmed=True)))
    assert response.explanation_mode == "llm_failed"
    assert response.explanation_error == "MODEL_EXPLANATION_INVALID"
    assert all("Hai phương án" not in line for line in response.explanation)


def test_natural_plan_review_keeps_full_engine_evidence(service, request_payload):
    from app.assistant.models import ParseRequest
    service.settings = service.settings.model_copy(update={"assistant_natural_explanations":True,"assistant_answer_review":True})
    service.llm = NaturalLLM()
    request = ParseRequest.model_validate(request_payload)
    parsed = asyncio.run(service.parse(request))
    response = asyncio.run(service.evaluate(EvaluateRequest(draft_id=parsed.draft_id,spec_hash=parsed.spec_hash,
        baseline=request.baseline, confirmed=True)))
    assert response.explanation_mode == "llm_plan" and response.llm_calls == 3
    assert response.evidence.source_hash == parsed.spec.source_hash


def test_editor_cannot_upgrade_a_failed_engine_candidate(service, request_payload):
    from app.assistant.models import ParseRequest
    class WrongEditor(NaturalLLM):
        async def complete(self, contract, messages):
            result = await super().complete(contract,messages)
            if contract is NaturalExplainPlan and "draft_to_review" in json.loads(messages[-1]["content"]):
                block = result.output.blocks[0]
                block.decision = "PASS" if block.decision != "PASS" else "FAIL"
            return result
    service.settings = service.settings.model_copy(update={"assistant_natural_explanations":True,"assistant_answer_review":True})
    service.llm = WrongEditor()
    request = ParseRequest.model_validate(request_payload)
    parsed = asyncio.run(service.parse(request))
    response = asyncio.run(service.evaluate(EvaluateRequest(draft_id=parsed.draft_id,spec_hash=parsed.spec_hash,
        baseline=request.baseline, confirmed=True)))
    assert response.explanation_mode == "llm_failed" and response.explanation_error == "MODEL_EXPLANATION_INVALID"
    assert all("Hai phương án" not in line for line in response.explanation)
