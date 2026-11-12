import asyncio
from copy import deepcopy
import json
from pathlib import Path
from time import monotonic

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.assistant.models import EvaluateRequest, ParseRequest, RequestPatch
from app.assistant.provider import AssistantError
from app.assistant.router import get_service
from app.assistant.store import DraftStore
from app.main import app
from app.services.lunarsight import planning
from app.mission.snapshot import SnapshotProvider
from app.mission.evaluation import evaluate
from conftest import FixtureLLM, default_patch


def run(coro):
    return asyncio.run(coro)


def confirmation(parsed, payload, **updates):
    return EvaluateRequest.model_validate({"draft_id": parsed.draft_id, "spec_hash": parsed.spec_hash,
        "baseline": payload["baseline"], "confirmed": True, **updates})


def test_two_calls_gated_engine_and_idempotent_replay(service, request_payload):
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert parsed.status == "READY" and parsed.spec.start_index == 288
    assert parsed.spec.end_utc == "2026-11-20T00:00:00Z"
    result = run(service.evaluate(confirmation(parsed, request_payload)))
    assert result.evidence.status == "INSUFFICIENT_DATA"
    assert result.evidence.recommended_site_id is None
    assert result.explanation_mode == "llm_plan"
    assert result.llm_calls == 2 and len(service.llm.calls) == 2
    assert run(service.evaluate(confirmation(parsed, request_payload))) == result
    assert len(service.llm.calls) == 2


def test_second_call_timeout_preserves_engine_result(service, request_payload):
    original = service.llm.complete
    async def timeout(contract, messages):
        if contract.__name__ == "ExplainPlan":
            raise AssistantError("OPENROUTER_TIMEOUT", 504)
        return await original(contract, messages)
    service.llm.complete = timeout
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    result = run(service.evaluate(confirmation(parsed, request_payload)))
    assert result.evidence.status == "INSUFFICIENT_DATA"
    assert result.explanation_mode == "llm_failed" and result.explanation_error == "OPENROUTER_TIMEOUT"
    assert not result.explanation_fact_ids and result.llm_calls == 2


def test_evidence_links_limits_and_timeline_event(service, request_payload):
    service.llm = FixtureLLM(default_patch(arrival_shift_days=0))
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    result = run(service.evaluate(confirmation(parsed, request_payload)))
    fact = result.evidence.facts["Site01_P1.earth"]
    assert fact["limit_hours"] == 0.8*72 and fact["requirement_type"] == "hard"
    assert fact["metric"] == "total_earth_los_hours" and fact["worst_interval"] is None
    blackout = result.evidence.facts["Site01_P1.blackout"]
    assert blackout["limit_hours"] == 6 and blackout["requirement_type"] == "soft"
    assert blackout["worst_interval"]["event_id"]
    assert blackout["worst_interval"]["duration_hours"] <= blackout["bounds"][1] + 1e-6


def test_snapshot_fixture_matches_science_sources():
    import hashlib
    root = Path(__file__).resolve().parents[2]
    sample = json.loads((root/"tests/fixtures/assistant/window_sample.json").read_text(encoding="utf-8"))
    assert len(sample["windows"]) == 6
    for path, checksum in sample["source_hashes"].items():
        assert hashlib.sha256((root/path).read_bytes()).hexdigest() == checksum
    jpl = json.loads((root/"tests/fixtures/assistant/jpl_samples.json").read_text(encoding="utf-8"))
    assert len(jpl["samples"]) == 4
    for series in jpl["samples"]:
        path = root/"data/cache/lunarsight/v0.2.0/raw"/series["archive_member"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == series["raw_sha256"]
        assert len(series["sample_rows"]) == 9


def test_no_feasible_never_becomes_pass(service, request_payload):
    service.llm = FixtureLLM(default_patch(arrival_shift_days=0))
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    result = run(service.evaluate(confirmation(parsed, request_payload)))
    assert result.evidence.status == "INSUFFICIENT_DATA"
    assert result.evidence.recommended_site_id is None
    assert result.evidence.apply_allowed is False
    assert all(c.decision == "INDETERMINATE" and c.nominal_sampled_decision == "FAIL" for c in result.evidence.candidates)


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(spec_hash="0"*64),
    lambda p: p.update(run_id="old-run"),
    lambda p: p.update(lead_code="FEASIBLE"),
    lambda p: p["blocks"][0].update(fact_ids=["invented.fact"]),
    lambda p: p["blocks"][0].update(fact_ids=["Site04_P1.dark"]),
])
def test_invalid_explanation_falls_back_without_third_call(service, request_payload, mutation):
    service.llm = FixtureLLM(mutate=mutation)
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    result = run(service.evaluate(confirmation(parsed, request_payload)))
    assert result.explanation_mode == "llm_failed" and result.explanation_error == "MODEL_EXPLANATION_INVALID"
    assert result.evidence.status == "INSUFFICIENT_DATA" and len(service.llm.calls) == 2


def test_missing_baseline_uses_zero_calls(service, request_payload):
    request_payload["baseline"] = None
    result = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert result.issues == ["MISSING_BASELINE"] and result.llm_calls == 0
    assert not service.llm.calls


@pytest.mark.parametrize("change,code", [
    ({"confirmed": False}, "CONFIRMATION_REQUIRED"),
    ({"spec_hash": "0"*64}, "SPEC_CHANGED"),
])
def test_confirmation_guards(service, request_payload, change, code):
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    with pytest.raises(AssistantError, match=code):
        run(service.evaluate(confirmation(parsed, request_payload, **change)))
    assert len(service.llm.calls) == 1


def test_stale_baseline_is_rejected(service, request_payload):
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    request_payload["baseline"]["constraints"]["max_darkness_hours"] = 14
    with pytest.raises(AssistantError, match="STALE_BASELINE"):
        run(service.evaluate(confirmation(parsed, request_payload)))
    assert len(service.llm.calls) == 1


def test_stale_source_is_rejected(service, request_payload, monkeypatch):
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    original = service.engine.capabilities
    monkeypatch.setattr(service.engine, "capabilities", lambda: {**original(), "source_hash": "changed"})
    with pytest.raises(AssistantError, match="STALE_DATASET"):
        run(service.evaluate(confirmation(parsed, request_payload)))


def test_expired_draft(service, request_payload):
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    service.drafts.get(parsed.draft_id).expires_at = monotonic()-1
    with pytest.raises(AssistantError, match="DRAFT_EXPIRED"):
        run(service.evaluate(confirmation(parsed, request_payload)))


def test_partial_data_does_not_hide_known_pass(service, request_payload, monkeypatch):
    original = SnapshotProvider.analyze
    def partial(self, target, request):
        if target.site_id == "Site04_P1":
            raise FileNotFoundError("simulated missing data")
        result = original(self, target, request)
        # Only this orchestration test injects accepted validation evidence.
        validation = {**result['validation'], 'passed': True, 'reason_codes': [], 'test_fixture': True}
        return {**result, **evaluate(request, result['timeline_frame'], validation)}
    monkeypatch.setattr(SnapshotProvider, "analyze", partial)
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    result = run(service.evaluate(confirmation(parsed, request_payload)))
    assert result.evidence.status == "FEASIBLE"
    assert result.evidence.coverage["indeterminate"] == 1
    assert result.evidence.candidates[1].issue == "DATA_NOT_READY"


def test_all_missing_data_has_no_recommendation(service, request_payload, monkeypatch):
    def missing(self, target, request):
        raise FileNotFoundError("simulated missing data")
    monkeypatch.setattr(SnapshotProvider, "analyze", missing)
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    result = run(service.evaluate(confirmation(parsed, request_payload)))
    assert result.evidence.status == "INSUFFICIENT_DATA"
    assert result.evidence.recommended_site_id is None and not result.evidence.apply_allowed


def test_uncertainty_straddling_threshold_is_indeterminate(service, request_payload, monkeypatch):
    original = SnapshotProvider.analyze
    def uncertain(self, target, request):
        result = original(self, target, request)
        frame = result['timeline_frame'].copy()
        frame['sun_state'] = '?'
        return {**result, 'timeline_frame': frame, **evaluate(request, frame, result['validation'])}
    monkeypatch.setattr(SnapshotProvider, "analyze", uncertain)
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    result = run(service.evaluate(confirmation(parsed, request_payload)))
    assert result.evidence.status == "INSUFFICIENT_DATA" and not result.evidence.apply_allowed


def test_corrupt_event_is_blocked_before_call_two(service, request_payload, monkeypatch):
    service.llm = FixtureLLM(default_patch(arrival_shift_days=0))
    original = SnapshotProvider.analyze
    def corrupt(self, target, request):
        result = original(self, target, request)
        result['timeline_frame'].iloc[0, result['timeline_frame'].columns.get_loc('end_utc')] = result['timeline_frame'].start_utc.iloc[0]
        return result
    monkeypatch.setattr(SnapshotProvider, "analyze", corrupt)
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    with pytest.raises(AssistantError, match="ENGINE_CONTRACT_ERROR"):
        run(service.evaluate(confirmation(parsed, request_payload)))
    assert len(service.llm.calls) == 1


@pytest.mark.parametrize("mutation", [
    lambda p: p["validation"].update(policy_version="wrong-version"),
    lambda p: p["coordinate"].update(latitude_deg=-80),
    lambda p: p["metrics_hours"].update(longest_dark_hours=[True, 10]),
    lambda p: p["constraint_checks"].update(max_darkness_hours="FAIL"),
])
def test_engine_contract_corruption_is_blocked(service, request_payload, monkeypatch, mutation):
    original = SnapshotProvider.analyze
    def corrupted(self, target, request):
        result = original(self, target, request)
        mutation(result)
        return result
    monkeypatch.setattr(SnapshotProvider, "analyze", corrupted)
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    with pytest.raises(AssistantError, match="ENGINE_CONTRACT_ERROR"):
        run(service.evaluate(confirmation(parsed, request_payload)))
    assert len(service.llm.calls) == 1


def test_schema_rejects_negative_and_extra_fields():
    with pytest.raises(ValidationError):
        default_patch(max_darkness_hours=-12)
    with pytest.raises(ValidationError):
        RequestPatch.model_validate({**default_patch().model_dump(), "invented": 1})


def test_http_routes_and_existing_health(service, request_payload):
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200
            assert "/api/analyze" in client.get("/openapi.json").json()["paths"]
            response = client.post("/api/assistant/parse", json=request_payload)
            assert response.status_code == 200
            parsed = response.json()
            result = client.post("/api/assistant/evaluate", json={"draft_id": parsed["draft_id"],
                "spec_hash": parsed["spec_hash"], "baseline": request_payload["baseline"], "confirmed": True})
            assert result.status_code == 200 and result.json()["llm_calls"] == 2
            assert client.post("/api/assistant/parse", json={**request_payload, "api_key": "reject"}).status_code == 422
    finally:
        app.dependency_overrides.clear()


CASES = json.loads((Path(__file__).parents[1]/"fixtures/assistant/prompts.json").read_text(encoding="utf-8"))
CASES += json.loads((Path(__file__).parents[1]/"fixtures/assistant/search_prompts.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_offline_prompt_contract_cases(service, request_payload, case):
    payload = deepcopy(request_payload)
    payload["text"] = case["text"]
    payload.update(case.get("context", {}))
    service.llm = FixtureLLM(RequestPatch.model_validate(case["patch"]))
    parsed = run(service.parse(ParseRequest.model_validate(payload)))
    assert parsed.status == case["expected_parse_status"]
    if parsed.status == "READY":
        for key, expected in case.get("expected_spec", {}).items():
            assert parsed.spec.model_dump()[key] == expected
        result = run(service.evaluate(confirmation(parsed, payload)))
        assert result.evidence.status == "INSUFFICIENT_DATA"
        assert all(c.validation.get("passed") is False for c in result.evidence.candidates)
    else:
        assert case["expected_issue"] in parsed.issues
