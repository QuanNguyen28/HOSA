import asyncio
import json
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, "backend")
from app.assistant.chat_models import ChatTurn, EvidenceClaim
from app.assistant.chat_service import ChatService, _safe_result
from app.assistant.interpretation import engine_evidence, claim_issues, explanation_view
from app.planning.models import CompareRequest
from app.planning.service import PlanningService


def point_result():
    return {"result_id":"verified-point-24h", "decision":"INDETERMINATE", "nominal_sampled_decision":"PASS",
        "metrics_hours":{"total_sun_hours":[20,22],"total_earth_los_hours":[19,20]},
        "request":{"site_id":"Site01_P1","start_utc":"2026-11-14T00:00:00Z","duration_hours":24,
                   "min_sunlit_fraction":.8,"min_earth_los_fraction":.75},
        "constraint_checks":{"min_sunlit_fraction":"PASS","min_earth_los_fraction":"PASS"},
        "soft_constraint_checks":{"max_darkness_hours":"FAIL"},
        "validation":{"passed":False,"reason_codes":["time_5min_vs_1min:SENSITIVITY_FAILED"]},
        "end_utc":"2026-11-15T00:00:00Z"}


def test_real_snapshot_evidence_preserves_all_decisions_and_candidate_identity():
    query=CompareRequest(site_ids=["Site01_P1","Site04_P1"],arrival_utc="2026-11-14T00:00:00Z",
                         min_sunlit_fraction=.8,min_earth_los_fraction=.8)
    result=PlanningService().compare(query)
    evidence=engine_evidence(_safe_result(result))
    assert evidence["source_hash"]==result.source_hash
    for candidate in result.candidates:
        facts=[f for f in evidence["facts"].values() if f["candidate_id"]==candidate.candidate_id]
        final=next(f for f in facts if f["kind"]=="decision")
        assert final["state"]==candidate.decision
        assert final["nominal_decision"]==candidate.nominal_sampled_decision
        for name,value in candidate.metrics.items():
            assert next(f for f in facts if f["kind"]=="metric."+name)["bounds_hours"]==value
        for name,state in candidate.constraint_states.items():
            assert next(f for f in facts if f["kind"]=="hard."+name)["state"]==state


def test_evidence_keeps_actual_duration_contact_and_soft_preference_separate():
    raw=point_result()
    windows=[{"start_utc":f"window-{index}","duration_minutes":4,"qualifies":False} for index in range(8)]
    raw["contact_analysis"]={"requirements":{"sampled_checks":{"min_contact_minutes":"FAIL"}},
                             "metrics":{"longest_contact_minutes_bounds":[4,6]},"scope":"geometry",
                             "visible_windows":windows}
    evidence=engine_evidence(_safe_result(raw))
    facts=list(evidence["facts"].values())
    assert next(f for f in facts if f["kind"]=="hard.min_sunlit_fraction")["duration_hours"]==24
    assert next(f for f in facts if f["kind"]=="hard.min_sunlit_fraction")["required_hours"]==pytest.approx(19.2)
    assert next(f for f in facts if f["kind"]=="soft.max_darkness_hours")["changes_hard_decision"] is False
    assert next(f for f in facts if f["kind"]=="contact")["metrics"]==raw["contact_analysis"]["metrics"]
    contact=next(f for f in facts if f["kind"]=="contact")
    assert contact["visible_windows"]==windows[:5] and contact["windows_truncated"] is True
    final=next(f for f in facts if f["kind"]=="decision")
    assert final["state"]=="INDETERMINATE" and final["nominal_decision"]=="PASS"


def test_claims_reject_other_result_and_relabelled_final_decision():
    evidence=engine_evidence(_safe_result(point_result()))
    key=next(k for k,v in evidence["facts"].items() if v["kind"]=="decision")
    assert "engine_state_mismatch" in claim_issues([EvidenceClaim(evidence_id=key,state="PASS")],evidence,True)
    assert "engine_evidence_not_in_result" in claim_issues([EvidenceClaim(evidence_id="another-result/x/decision",state="PASS")],evidence,True)


def test_mission_bounded_pass_is_distinct_from_full_validation_in_chat():
    raw = point_result()
    raw['decision'] = 'PASS'
    raw['validation']['mission_path'] = {'passed': True,
        'scope': 'requested_sampled_sun_and_earth_paths_only',
        'metrics_hours': {'total_sun_hours': [20, 22]}}
    raw['resolution'] = {'enabled': True, 'status': 'resolved'}
    summary = _safe_result(raw)
    assert summary['resolution'] == raw['resolution']
    evidence = engine_evidence(summary)
    detail = next(f for f in evidence['facts'].values() if f['kind'] == 'decision')
    assert detail['mission_bounds'] == raw['validation']['mission_path']['metrics_hours']
    view = explanation_view(evidence, 'Vì sao điểm này đạt?')
    final = next(f for f in view['facts'].values() if f['kind'] == 'decision')
    assert final['state'] == 'PASS' and final['validation_passed'] is False
    assert final['mission_path_passed'] is True
    assert final['validation_scope'] == 'requested_sampled_sun_and_earth_paths_only'


class ScriptedLLM:
    last_provider="nvidia"
    events=[]
    def __init__(self, outputs):
        self.outputs=iter(outputs)
        self.messages=[]
    async def complete(self, contract, messages):
        self.messages.append(messages)
        return SimpleNamespace(output=next(self.outputs))


def service(monkeypatch,llm):
    knowledge=SimpleNamespace(search=lambda text,limit: [{"source_id":"doc","path":"guide","excerpt":"source"}])
    instance=ChatService(llm,knowledge)
    monkeypatch.setattr(instance,"_ensure_index",lambda:None)
    monkeypatch.setattr(instance.planner,"capabilities",lambda:{})
    async def execute(*args):
        return point_result()
    monkeypatch.setattr(instance,"_execute",execute)
    return instance


def test_general_chat_uses_current_brand_without_rewriting_source_paths(monkeypatch):
    llm = ScriptedLLM([ChatTurn(
        intent="knowledge", source_ids=["doc"],
        answer="Trợ lý HOSA/LunarSight chỉ hỗ trợ dự án LunarSight. Xem `data/processed/lunarsight/v0.2.0`.",
    )])
    result = asyncio.run(service(monkeypatch, llm).respond(
        "Đề xuất cho tôi vài quán ăn ở Hà Nội", [], {}, knowledge_only=True,
    ))
    assert result["answer"] == "Trợ lý HOSA chỉ hỗ trợ dự án HOSA. Xem `data/processed/lunarsight/v0.2.0`."
    assert result["citations"][0]["source_id"] == "doc"


@pytest.mark.parametrize(("text", "intent"), [
    ("đề xuất điểm hạ cánh", "clarify"),
    ("so sánh 2 điểm 04 và 01", "compare"),
])
def test_general_chat_redirects_mission_requests_without_using_model_claims(monkeypatch, text, intent):
    llm = ScriptedLLM([ChatTurn(intent=intent, answer="Site04 chắc chắn đạt.",
                                source_ids=["invented"], query={"unverified": True})])
    instance = service(monkeypatch, llm)

    async def unexpected(*args):
        pytest.fail("General chat must not run an analysis before confirmation")

    monkeypatch.setattr(instance, "_execute", unexpected)
    result = asyncio.run(instance.respond(text, [], {}, knowledge_only=True))
    assert result["status"] == "needs_input" and len(llm.messages) == 1
    assert result["next_action"] == "prepare_mission" and "chắc chắn đạt" not in result["answer"]
    assert result["query"] is None and not result["citations"]


def test_general_chat_never_displays_unverified_knowledge_answer(monkeypatch):
    bad = ChatTurn(intent="knowledge", answer="Unsupported result.", source_ids=["invented"])
    llm = ScriptedLLM([bad, bad])
    result = asyncio.run(service(monkeypatch, llm).respond("HOSA giúp tôi điều gì?", [], {}, knowledge_only=True))
    assert result["status"] == "partial" and result["explanation_error"] == "MODEL_GROUNDING_INVALID"
    assert "chưa xác minh" in result["answer"] and not result["citations"]


def explained(state="INDETERMINATE",evidence_id=None):
    key=evidence_id or next(k for k,v in engine_evidence(_safe_result(point_result()))["facts"].items() if v["kind"]=="decision")
    return ChatTurn(intent="explain",answer="Chưa thể xác nhận phương án đạt vì kiểm định độ nhạy chưa đạt, dù số liệu danh định đáp ứng yêu cầu.",
                    evidence_claims=[EvidenceClaim(evidence_id=key,state=state)])


def test_engine_explanation_repairs_wrong_decision_without_recomputing(monkeypatch):
    llm=ScriptedLLM([ChatTurn(intent="point",query=point_result()["request"]),explained("PASS"),explained()])
    instance=service(monkeypatch,llm)
    result=asyncio.run(instance.respond("Vì sao chưa thể kết luận?",[],{}))
    assert result["status"]=="completed"
    assert result["result"]["decision"]=="INDETERMINATE"
    assert result["evidence_claims"][0]["state"]=="INDETERMINATE"
    assert len(llm.messages)==3
    assert "engine_state_mismatch" in llm.messages[-1][-1]["content"]


def test_invalid_explanation_retains_scientific_result_as_partial(monkeypatch):
    llm=ScriptedLLM([ChatTurn(intent="point",query=point_result()["request"]),explained("PASS"),explained("PASS")])
    result=asyncio.run(service(monkeypatch,llm).respond("Tính giúp tôi",[],{}))
    assert result["status"]=="partial"
    assert result["explanation_error"]=="MODEL_GROUNDING_INVALID"
    assert result["result"]["decision"]=="INDETERMINATE"
    assert result["evidence_claims"]==[]


def test_followup_uses_saved_evidence_without_new_compute(monkeypatch):
    reply=explained()
    reply.query={"start_utc":"2026-12-01T00:00:00Z"}
    llm=ScriptedLLM([reply])
    instance=service(monkeypatch,llm)
    async def unexpected(*args):
        pytest.fail("An explanation-only follow-up must not recompute")
    monkeypatch.setattr(instance,"_execute",unexpected)
    evidence=engine_evidence(_safe_result(point_result()))
    result=asyncio.run(instance.respond("Vì sao chưa thể kết luận?",[],{"last_engine_evidence":evidence}))
    assert result["status"]=="completed" and result["result"] is None
    payload=json.loads(llm.messages[0][1]["content"])
    assert payload["working_query"]["last_engine_evidence"]["result_id"]==point_result()["result_id"]
    assert result["evidence"]==evidence
    assert result["query"] is None  # A prose explanation cannot replace the computed working query.


def test_missing_required_date_is_repaired_to_clarification_before_compute(monkeypatch):
    llm=ScriptedLLM([ChatTurn(intent="compare",query={"site_ids":["Site01_P1","Site04_P1"],"min_sunlit_fraction":.8}),
                    ChatTurn(intent="clarify",clarification="Bạn muốn bắt đầu nhiệm vụ vào ngày và giờ nào (UTC)?")])
    instance=service(monkeypatch,llm)
    async def unexpected(*args):
        pytest.fail("Do not execute a query missing a required date")
    monkeypatch.setattr(instance,"_execute",unexpected)
    result=asyncio.run(instance.respond("So sánh hai site với 80% nắng",[],{}))
    assert result["status"]=="needs_input"
    assert "arrival_utc" in llm.messages[1][-1]["content"]


def test_explanation_has_no_arbitrary_length_limit(monkeypatch):
    verbose=explained()
    verbose.answer=" ".join(["evidence"]*180)
    llm=ScriptedLLM([ChatTurn(intent="point",query=point_result()["request"]),verbose])
    result=asyncio.run(service(monkeypatch,llm).respond("Phân tích và giải thích ngắn bằng vài câu",[],{}))
    assert result["answer"]==verbose.answer
    assert result["result"]["result_id"]==point_result()["result_id"]
    assert len(llm.messages)==2


def test_explanation_focus_preserves_states_and_only_includes_numbers_when_requested():
    evidence=engine_evidence(_safe_result(point_result()))
    qualitative=explanation_view(evidence,"Vì sao chưa thể kết luận phương án đạt?")
    assert set(qualitative["facts"])==set(evidence["facts"])
    for key,fact in qualitative["facts"].items():
        assert fact["state"]==evidence["facts"][key]["state"]
        assert "bounds_hours" not in fact and "required_hours" not in fact
    assert explanation_view(evidence,"Có bao nhiêu giờ nhìn thấy Trái Đất? Chi tiết số liệu.")==evidence
    assert explanation_view(evidence,"Giải thích bằng chứng thay vì liệt kê số liệu")["detail_mode"]=="qualitative"
    assert explanation_view(evidence,"Không giới hạn độ dài, chỉ cần ít số liệu")["detail_mode"]=="qualitative"


def test_answer_review_uses_original_sources_and_returns_validated_edit(monkeypatch):
    draft=ChatTurn(intent="knowledge",answer="A generic draft.",source_ids=["doc"])
    edit=ChatTurn(intent="knowledge",answer="A focused explanation grounded in the source.",source_ids=["doc"])
    llm=ScriptedLLM([draft,edit])
    instance=service(monkeypatch,llm)
    instance.review_answers=True
    result=asyncio.run(instance.respond("What is the point of HOSA?",[],{},knowledge_only=True))
    assert result["answer"]==edit.answer and len(llm.messages)==2
    assert "draft_to_review" in llm.messages[1][-1]["content"]
    assert "retrieved_sources" in llm.messages[1][1]["content"]


def test_answer_review_cannot_turn_knowledge_into_new_computation(monkeypatch):
    draft=ChatTurn(intent="knowledge",answer="Original answer.",source_ids=["doc"])
    bad=ChatTurn(intent="point",answer="Do a new mission.",query={"unverified":True})
    llm=ScriptedLLM([draft,bad,draft])
    instance=service(monkeypatch,llm)
    instance.review_answers=True
    async def unexpected(*args):
        pytest.fail("The editor cannot initiate an engine call")
    monkeypatch.setattr(instance,"_execute",unexpected)
    result=asyncio.run(instance.respond("What is HOSA?",[],{},knowledge_only=True))
    assert result["intent"]=="knowledge" and result["query"] is None
    assert "review_changed_routing" in llm.messages[-1][-1]["content"]
