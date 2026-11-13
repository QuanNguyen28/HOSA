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
from app.mission.targets import compare_sites, coordinates_for_site
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


def test_chat_handoff_asks_only_for_missing_start_then_keeps_sites(service, request_payload):
    request_payload.update(text="so sánh 2 điểm 04 và 01", require_explicit_start=True)
    service.llm = FixtureLLM(default_patch(
        arrival_shift_days=None, site_ids=["Site04_P1", "Site01_P1"],
        source_quotes=["04 và 01"],
    ))
    missing = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert missing.status == "NEEDS_INPUT"
    assert [q.field for q in missing.questions] == ["arrival_utc"]
    assert missing.draft_id is None

    date = "2026-11-17T00:00:00Z"
    request_payload["clarifications"] = [{"question": missing.questions[0].question, "answer": date}]
    service.llm = FixtureLLM(default_patch(
        arrival_shift_days=None, arrival_utc=date, site_ids=["Site04_P1", "Site01_P1"],
        source_quotes=["04 và 01", date],
    ))
    ready = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert ready.status == "READY" and ready.spec.arrival_utc == date
    assert set(ready.spec.site_ids) == {"Site04_P1", "Site01_P1"}
    assert service.llm.calls == ["RequestPatch"]  # Review only; no evaluation.


def test_clps_chat_handoff_keeps_both_names_and_uses_coordinate_planner(service, request_payload, monkeypatch):
    request_payload.update(text="so sánh IM1 IM2", require_explicit_start=True)
    service.llm = FixtureLLM(default_patch(
        arrival_shift_days=None, site_ids=["IM1", "IM2"], source_quotes=["IM1 IM2"],
    ))
    missing = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert missing.status == "NEEDS_INPUT"
    assert [q.field for q in missing.questions] == ["arrival_utc"]
    assert missing.draft_id is None

    date = "2026-11-17T00:05:00Z"
    request_payload["clarifications"] = [{"question": missing.questions[0].question, "answer": date}]
    service.llm = FixtureLLM(default_patch(
        arrival_shift_days=None, arrival_utc=date, site_ids=["Athena"],
        source_quotes=["IM1 IM2", date],
    ))
    ready = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert ready.status == "READY" and ready.spec.arrival_utc == date
    assert ready.spec.site_ids == ["im1-odysseus", "im2-athena"]
    assert ready.spec.data_source == "coordinate" and ready.spec.start_index is None
    assert service.llm.calls == ["RequestPatch"]

    class PlannerReached(Exception):
        pass

    def compare(query):
        assert query.site_ids == ready.spec.site_ids
        assert query.data_source == "coordinate" and query.expected_source_hash is None
        raise PlannerReached

    monkeypatch.setattr(service.engine.planner, "compare", compare)
    with pytest.raises(PlannerReached):
        service.engine.evaluate(ready.spec, "test-run", ready.spec_hash)


@pytest.mark.parametrize("site_id,site", compare_sites().items())
def test_each_compare_site_is_supported_in_chat(service, request_payload, site_id, site):
    date = "2026-11-17T00:05:00Z"
    request_payload.update(text=f"Phân tích {site['name']} lúc {date}", require_explicit_start=True)
    service.llm = FixtureLLM(default_patch(
        arrival_shift_days=None, arrival_utc=date, site_ids=None,
        source_quotes=[site["name"], date],
    ))
    ready = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert ready.status == "READY"
    assert ready.spec.site_ids == [site_id] and ready.spec.data_source == "coordinate"
    assert coordinates_for_site(site_id) == {"latitude_deg": site["lat"], "longitude_e_deg": site["lon"] % 360}


def test_chat_keeps_distinct_names_and_mixed_snapshot_target(service, request_payload):
    date = "2026-11-17T00:05:00Z"
    for text, expected in [
        ("Mons Mouton và Mons Mouton Plateau", ["mons-mouton", "mons-mouton-plateau"]),
        ("Site01_P1 và Connecting Ridge", ["Site01_P1", "connecting-ridge"]),
    ]:
        request_payload.update(text=f"So sánh {text} lúc {date}", require_explicit_start=True)
        service.llm = FixtureLLM(default_patch(
            arrival_shift_days=None, arrival_utc=date, site_ids=None, source_quotes=[text, date],
        ))
        ready = run(service.parse(ParseRequest.model_validate(request_payload)))
        assert ready.status == "READY"
        assert ready.spec.site_ids == expected and ready.spec.data_source == "coordinate"


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
    assert result.llm_calls == 2
    assert result.explanation[0].startswith("Tóm tắt từ kết quả tính toán")
    assert all(key in result.evidence.facts for key in result.explanation_fact_ids)


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
    assert result.evidence.status == "NO_FEASIBLE_IN_EVALUATED_SET"
    assert result.evidence.apply_allowed is False
    assert all(c.decision == "FAIL" and c.nominal_sampled_decision == "FAIL" for c in result.evidence.candidates)
    assert all(c.validation["passed"] is False for c in result.evidence.candidates)


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(spec_hash="0"*64),
    lambda p: p.update(run_id="old-run"),
    lambda p: p.update(lead_code="FEASIBLE"),
    lambda p: p["blocks"][0].update(fact_ids=["invented.fact"]),
    lambda p: p["blocks"][0].update(fact_ids=["Site04_P1.dark"]),
])
def test_invalid_explanation_remains_failed_after_one_repair(service, request_payload, mutation):
    service.llm = FixtureLLM(mutate=mutation)
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    result = run(service.evaluate(confirmation(parsed, request_payload)))
    assert result.explanation_mode == "llm_failed" and result.explanation_error == "MODEL_EXPLANATION_INVALID"
    assert result.evidence.status == "INSUFFICIENT_DATA" and len(service.llm.calls) == 3
    assert result.llm_calls == 3


def test_empty_explanation_is_repaired_with_all_indeterminate_candidates(service, request_payload):
    original = service.llm.complete
    seen = []

    async def incomplete_once(contract, messages):
        result = await original(contract, messages)
        if contract.__name__ != "ExplainPlan":
            return result
        payload = json.loads(messages[-1]["content"])
        seen.append(payload)
        assert payload["candidate_count"] == 2
        assert all(row["decision"] == "INDETERMINATE" and row["allowed_reasons"]
                   for row in payload["candidates"])
        if len(seen) == 1:
            result.output.blocks.clear()
        else:
            assert "previous plan failed validation" in messages[0]["content"]
        return result

    service.llm.complete = incomplete_once
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    result = run(service.evaluate(confirmation(parsed, request_payload)))
    assert len(seen) == 2 and result.llm_calls == 3
    assert result.explanation_mode == "llm_plan" and result.explanation_error is None
    assert all(any(site in line for line in result.explanation)
               for site in ("Site01_P1", "Site04_P1"))
    assert not result.evidence.apply_allowed


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
def test_offline_prompt_contract_cases(service, request_payload, case, monkeypatch):
    payload = deepcopy(request_payload)
    payload["text"] = case["text"]
    payload.update(case.get("context", {}))
    service.llm = FixtureLLM(RequestPatch.model_validate(case["patch"]))
    parsed = run(service.parse(ParseRequest.model_validate(payload)))
    assert parsed.status == case["expected_parse_status"]
    if parsed.status == "READY":
        for key, expected in case.get("expected_spec", {}).items():
            assert parsed.spec.model_dump()[key] == expected
        if parsed.spec.data_source == "coordinate":
            from app.core.errors import DomainError
            def unavailable(*args): raise DomainError('HORIZONS_CACHE_MISS', 503)
            monkeypatch.setattr('app.point_analysis.service.calculate', unavailable)
        result = run(service.evaluate(confirmation(parsed, payload)))
        expected = "NO_FEASIBLE_IN_EVALUATED_SET" if case["id"] == "A05" else "INSUFFICIENT_DATA"
        assert result.evidence.status == expected
        assert all(c.validation.get("passed") is False for c in result.evidence.candidates)
    else:
        assert case["expected_issue"] in parsed.issues


def test_revalidation_is_sealed_in_draft_and_missing_network_stays_unknown(service, request_payload, monkeypatch):
    from app.core.errors import DomainError
    request_payload['resolve_indeterminate'] = True
    def unavailable(*args):
        raise DomainError('HORIZONS_UNAVAILABLE', 502)
    monkeypatch.setattr('app.point_analysis.service.calculate', unavailable)
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert parsed.status == 'READY' and parsed.spec.resolve_indeterminate is True
    assert parsed.spec.source_hash == service.engine.capabilities(resolve_indeterminate=True)['source_hash']
    from app.planning.models import CompareRequest
    for selected in [['Site01_P1'], ['Site04_P1'], ['Site01_P1', 'Site04_P1']]:
        query = CompareRequest(site_ids=selected, arrival_utc=parsed.spec.arrival_utc,
            min_sunlit_fraction=0.8, illumination_model='sun_center', resolve_indeterminate=True)
        assert service.engine.planner.source_capabilities(query)['source_hash'] == parsed.spec.source_hash
    result = run(service.evaluate(confirmation(parsed, request_payload)))
    assert len(service.llm.calls) == 2 and result.llm_calls == 2
    assert not result.evidence.apply_allowed
    for candidate in result.evidence.candidates:
        assert candidate.decision == 'INDETERMINATE'
        assert candidate.resolution['status'] == 'unresolved'
        assert candidate.resolution['error_code'] == 'HORIZONS_UNAVAILABLE'
        assert candidate.resolution['origin']['provider'] == 'snapshot'
    assert any('kiểm chứng bổ sung' in text for text in result.explanation)
    assert any(key.endswith('.validation') for key in result.explanation_fact_ids)


@pytest.mark.parametrize('site_id', ['Site04_P1', 'haworth'])
def test_merged_chat_preserves_long_end_date_and_validation_across_turns(service, request_payload, site_id):
    start, end = '2026-11-17T00:00:00Z', '2026-11-27T00:00:00Z'
    request_payload.update(text=f'Phân tích {site_id} từ {start} đến {end}',
                           resolve_indeterminate=True, selected_site_ids=[site_id])
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, arrival_utc=start,
        mission_end_utc=end, site_ids=[site_id], source_quotes=[start, end]))
    ready = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert ready.status == 'READY' and ready.spec.duration_hours == 240
    assert ready.spec.data_source == 'coordinate' and ready.spec.resolve_indeterminate
    assert ready.spec.site_ids == [site_id] and ready.spec.end_utc == end
    request_payload['baseline'].update(arrival_utc=start, duration_hours=240, current_site_id=site_id)
    request_payload['text'] = 'Đổi yêu cầu nắng lên 90%, giữ lịch và điểm.'
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, site_scope='unspecified',
        min_sunlit_fraction=.9, source_quotes=['90%']))
    followup = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert followup.status == 'READY'
    assert followup.spec.duration_hours == 240 and followup.spec.end_utc == end
    assert followup.spec.site_ids == [site_id] and followup.spec.min_sunlit_fraction == .9
    assert followup.spec.resolve_indeterminate


@pytest.mark.parametrize('end,hours', [
    ('2027-11-27T00:00:00Z', 240),
    ('2028-11-17T00:00:00Z', 8784),
])
def test_compare_two_sites_for_entire_explicit_interval(service, request_payload, monkeypatch, end, hours):
    start = '2027-11-17T00:00:00Z'
    sites = ['im1-odysseus', 'im2-athena']
    request_payload.update(text=f'So sánh IM-1 với IM-2 từ {start} đến {end}', selected_site_ids=sites)
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, arrival_utc=start,
        mission_end_utc=end, site_scope='selected', site_ids=sites, source_quotes=[start, end]))
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert parsed.status == 'READY'
    assert parsed.spec.site_ids == sites and parsed.spec.duration_hours == hours
    assert parsed.spec.search_from_utc is None and parsed.spec.search_until_utc is None
    def capture(query):
        assert query.site_ids == sites and query.data_source == 'coordinate'
        for target in query.mission_targets():
            mission = query.mission(target)
            assert mission.start_utc == start and mission.end_utc == end
            assert mission.duration_hours == hours
        raise RuntimeError('comparison_contract_verified')
    monkeypatch.setattr(service.engine.planner, 'compare', capture)
    with pytest.raises(RuntimeError, match='comparison_contract_verified'):
        service.engine.evaluate(parsed.spec, parsed.draft_id, parsed.spec_hash)


def test_named_coordinate_catalog_change_invalidates_draft(service, request_payload, monkeypatch):
    from app.mission.targets import compare_sites
    request_payload.update(text='Phân tích Haworth lúc 2026-11-17T00:00:00Z',
                           selected_site_ids=['haworth'])
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, arrival_utc='2026-11-17T00:00:00Z',
        site_ids=['haworth'], source_quotes=['Haworth']))
    parsed = run(service.parse(ParseRequest.model_validate(request_payload)))
    assert parsed.status == 'READY'
    changed = deepcopy(compare_sites())
    changed['haworth']['lat'] += .001
    monkeypatch.setattr('app.mission.targets.compare_sites', lambda: changed)
    with pytest.raises(AssistantError, match='STALE_DATASET'):
        run(service.evaluate(confirmation(parsed, request_payload)))
