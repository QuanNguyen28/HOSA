import asyncio

import pytest

from app.assistant.models import EvaluateRequest, ExplainPlan, ParseRequest
from app.assistant.provider import AssistantError
from app.assistant.explanations import valid_plan
from conftest import FixtureLLM, default_patch


def confirm(parsed, payload):
    return EvaluateRequest(draft_id=parsed.draft_id, spec_hash=parsed.spec_hash,
        baseline=payload["baseline"], confirmed=True)


def test_llm_search_uses_two_calls_and_distinct_window_facts(service, request_payload):
    request_payload["text"] = "Cho phép đổi ngày hạ cánh trong khoảng 2026-11-17T00:00:00Z đến trước 2026-11-24T00:00:00Z, giữ phần cứng và đổi điểm trong vùng này."
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, source_quotes=["Cho phép đổi ngày"],
        search_from_utc="2026-11-17T00:00:00Z", search_until_utc="2026-11-24T00:00:00Z"))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert parsed.status == "READY"
    result = asyncio.run(service.evaluate(confirm(parsed, request_payload)))
    assert result.llm_calls == 2 and len(service.llm.calls) == 2
    assert result.explanation_mode == "llm_plan"
    assert result.evidence.status == "FEASIBLE"
    assert len({c.candidate_id for c in result.evidence.candidates}) == len(result.evidence.candidates)
    assert all("@" in key for key in result.evidence.facts)
    assert result.evidence.recommended_candidate_id


def test_exact_date_does_not_expand_search_scope(service, request_payload):
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    result = asyncio.run(service.evaluate(confirm(parsed, request_payload)))
    assert parsed.spec.search_from_utc is None
    assert result.evidence.coverage["candidate_total"] == 2
    assert all(c.start_index == 288 for c in result.evidence.candidates)


def test_incomplete_search_range_requires_input(service, request_payload):
    service.llm = FixtureLLM(default_patch(search_from_utc="2026-11-17T00:00:00Z"))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert parsed.issues == ["INCOMPLETE_SEARCH_RANGE"] and parsed.llm_calls == 1


def test_failed_draft_is_cached_as_failure_instead_of_stuck_busy(service, request_payload, monkeypatch):
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    calls = []
    def fail(*args):
        calls.append(1)
        raise AssistantError("ENGINE_CONTRACT_ERROR",502)
    monkeypatch.setattr(service.engine, "evaluate", fail)
    for _ in range(2):
        with pytest.raises(AssistantError, match="ENGINE_CONTRACT_ERROR"):
            asyncio.run(service.evaluate(confirm(parsed, request_payload)))
    assert len(calls) == 1 and len(service.llm.calls) == 1


def test_explanation_cannot_explain_failure_with_passing_condition(service, request_payload):
    service.llm = FixtureLLM(default_patch(arrival_shift_days=0))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    result = asyncio.run(service.evaluate(confirm(parsed, request_payload)))
    evidence = result.evidence
    plan = ExplainPlan(run_id=evidence.run_id, spec_hash=evidence.spec_hash, lead_code=evidence.status,
        blocks=[{"site_id":c.site_id,"candidate_id":c.candidate_id,"reason_code":"DARKNESS","fact_ids":[c.candidate_id+".dark"]}
                for c in evidence.candidates])
    assert not valid_plan(plan, evidence)


def test_io_failure_does_not_leave_draft_permanently_busy(service, request_payload, monkeypatch):
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    calls = []
    def fail(*args):
        calls.append(1)
        raise OSError("simulated storage unavailable")
    monkeypatch.setattr(service.engine, "evaluate", fail)
    for _ in range(2):
        with pytest.raises(AssistantError, match="DATA_NOT_READY"):
            asyncio.run(service.evaluate(confirm(parsed, request_payload)))
    assert len(calls) == 1


def test_explanation_reports_the_selected_sunlight_objective(service, request_payload):
    service.llm = FixtureLLM(default_patch(rank_by="total_sun_hours"))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    result = asyncio.run(service.evaluate(confirm(parsed, request_payload)))
    assert any("có nắng" in line for line in result.explanation)
    assert any(key.endswith(".sun") for key in result.explanation_fact_ids)


def test_parse_issues_include_proposed_fields_for_user_review(service, request_payload):
    service.llm = FixtureLLM(default_patch(search_from_utc="2026-11-17T00:00:00Z"))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert parsed.status == "NEEDS_INPUT" and parsed.patch is not None
    assert parsed.patch.search_from_utc == "2026-11-17T00:00:00Z"
