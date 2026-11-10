import asyncio
import json

from app.assistant.models import ClarificationTurn, EvaluateRequest, ParseRequest, RequestPatch
from app.assistant.clarification import questions_for
from conftest import FixtureLLM, default_patch
from scripts.assistant_chat import run_console
from scripts.demo_provider import DEMO_PROMPT, DemoLLM


class ClarifyingLLM(FixtureLLM):
    async def complete(self, contract, messages):
        if contract is RequestPatch:
            request = json.loads(messages[-1]["content"])["request"]
            if request["clarifications"]:
                self.patch = default_patch(arrival_shift_days=None, arrival_utc="2026-11-17T00:00:00Z",
                    source_quotes=["2026-11-17T00:00:00Z"])
            else:
                self.patch = default_patch(arrival_shift_days=None, unresolved_fields=["year","time","timezone"],
                    source_quotes=["17/11"], clarification_questions=[{"field":"arrival_utc","question":"Ngày 17/11 thuộc năm nào, lúc mấy giờ và theo múi giờ nào?"}])
        return await super().complete(contract,messages)


def test_missing_information_questions_then_answer_then_evaluate(service, request_payload):
    request_payload["text"] = DEMO_PROMPT
    service.llm = ClarifyingLLM()
    first = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert first.status == "NEEDS_INPUT" and first.questions and first.draft_id is None
    assert len(service.llm.calls) == 1
    assert "năm" in first.questions[0].question
    second_request = ParseRequest.model_validate({**request_payload, "clarifications":[
        {"question":first.questions[0].question,"answer":"2026-11-17T00:00:00Z"}]})
    second = asyncio.run(service.parse(second_request))
    assert second.status == "READY" and second.spec.start_index == 288 and not second.questions
    result = asyncio.run(service.evaluate(EvaluateRequest(draft_id=second.draft_id,spec_hash=second.spec_hash,
                                                          baseline=request_payload["baseline"],confirmed=True)))
    assert result.evidence.status == "INSUFFICIENT_DATA"
    assert service.llm.calls == ["RequestPatch","RequestPatch","ExplainPlan"]


def test_model_question_alone_blocks_evaluation(service, request_payload):
    service.llm = FixtureLLM(default_patch(clarification_questions=[
        {"field":"arrival_utc","question":"Bạn muốn lùi bao nhiêu ngày?"}]))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert parsed.status == "NEEDS_INPUT" and parsed.draft_id is None
    assert parsed.questions[0].field == "arrival_utc"


def test_source_quote_cannot_come_from_assistant_question(service, request_payload):
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None,arrival_utc="2026-11-17T00:00:00Z",
        source_quotes=["2026-11-17T00:00:00Z"]))
    request = ParseRequest.model_validate({**request_payload,"clarifications":[
        {"question":"Ví dụ 2026-11-17T00:00:00Z?","answer":"Tôi chưa chốt giờ."}]})
    parsed = asyncio.run(service.parse(request))
    assert parsed.issues == ["UNSUPPORTED_SOURCE_QUOTE"]


def test_questions_have_backend_fallbacks_and_ignore_unrelated_model_question():
    patch = default_patch(unresolved_fields=["year"],clarification_questions=[
        {"field":"constraints","question":"Ngưỡng tối bao nhiêu?"}])
    result = questions_for("UNRESOLVED_FIELDS",patch)
    assert result[0].field == "year" and "năm" in result[0].question
    assert questions_for("MISSING_REGION")[0].field == "site_scope"
    assert "15 phút" in questions_for("OFF_START_GRID")[0].question


class CountedDemo(DemoLLM):
    def __init__(self):
        self.calls = []
    async def complete(self, contract, messages):
        self.calls.append(contract.__name__)
        return await super().complete(contract,messages)


def test_terminal_demo_question_answer_confirmation_result(service, request_payload):
    service.llm = CountedDemo()
    answers = iter(["","2026-11-17T00:00:00Z","y","/quit"])
    output = []
    code = run_console(service,request_payload,ask=lambda _: next(answers),say=output.append,demo=True)
    assert code == 0
    assert any("Cần làm rõ" in line for line in output)
    assert any("INSUFFICIENT_DATA" in line for line in output)
    assert any("API thật = 0" in line for line in output)
    assert service.llm.calls == ["RequestPatch","RequestPatch","ExplainPlan"]


def test_terminal_decline_never_runs_engine_or_explanation(service, request_payload, monkeypatch):
    service.llm = CountedDemo()
    def forbidden(*args):
        raise AssertionError("Engine must not run before confirmation")
    monkeypatch.setattr(service.engine,"evaluate",forbidden)
    answers = iter(["","2026-11-17T00:00:00Z","n","/quit"])
    output = []
    assert run_console(service,request_payload,ask=lambda _: next(answers),say=output.append,demo=True)==0
    assert service.llm.calls == ["RequestPatch","RequestPatch"]


def test_terminal_honors_clarification_limit(service, request_payload):
    service.llm = CountedDemo()
    answers = iter(["","chưa biết","/quit"])
    output = []
    run_console(service,request_payload,ask=lambda _: next(answers),say=output.append,demo=True,max_clarifications=1)
    assert any("giới hạn hỏi lại" in line for line in output)
    assert service.llm.calls == ["RequestPatch","RequestPatch"]
