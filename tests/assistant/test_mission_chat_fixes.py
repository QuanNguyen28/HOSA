"""Regressions for mission-planning chat: search budget, catalog site names, explanation margins."""
import asyncio
import json

import pytest

from app.assistant.interpretation import engine_evidence, explanation_view
from app.assistant.models import EvaluateRequest, ParseRequest, utc
from app.assistant.normalization import search_step_minutes
from app.assistant.provider import AssistantError
from app.assistant.prompts import explain_messages
from app.assistant.start_time import start_context
from conftest import FixtureLLM, default_patch


@pytest.mark.parametrize("start,end,targets,expected", [
    ("2026-11-14T00:00:00Z", "2026-11-15T00:00:00Z", 1, 15),   # 96 starts fit the default grid
    ("2026-11-14T00:00:00Z", "2026-11-15T00:00:00Z", 2, 30),   # 2 sites x 48 starts
    ("2026-11-17T00:00:00Z", "2026-11-24T00:00:00Z", 1, 80),   # one week, 126 starts
    ("2026-12-01T00:00:00Z", "2026-12-31T00:00:00Z", 1, 360),  # 30 days, 120 starts
])
def test_search_step_fits_engine_budget(start, end, targets, expected):
    step = search_step_minutes(start, end, targets)
    assert step == expected and step % 5 == 0
    minutes = int((utc(end) - utc(start)).total_seconds() / 60)
    assert minutes % step == 0 and minutes // step * targets <= 128


def test_requested_step_is_never_coarsened():
    assert search_step_minutes("2026-11-14T00:00:00Z", "2026-11-15T00:00:00Z", 1, 60) == 60
    with pytest.raises(AssistantError, match="SEARCH_TOO_LARGE"):
        search_step_minutes("2026-11-14T00:00:00Z", "2026-11-24T00:00:00Z", 1, 15)
    with pytest.raises(AssistantError, match="INVALID_SEARCH_STEP"):
        search_step_minutes("2026-11-14T00:00:00Z", "2026-11-15T00:00:00Z", 1, 35)


def test_range_beyond_daily_step_budget_asks_to_narrow():
    with pytest.raises(AssistantError, match="SEARCH_TOO_LARGE"):
        search_step_minutes("2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z", 1)


def solar_disc(payload):
    payload["baseline"]["illumination_model"] = "solar_disc"
    return payload


def test_week_search_gets_a_step_instead_of_engine_rejection(service, request_payload):
    request_payload["text"] = "Tìm thời điểm bắt đầu tốt nhất cho Connecting Ridge từ 17/11/2026 00:00 UTC đến 24/11/2026 00:00 UTC"
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, site_ids=["connecting-ridge"],
        source_quotes=["Tìm thời điểm bắt đầu tốt nhất"], max_darkness_hours=None,
        search_from_utc="2026-11-17T00:00:00Z", search_until_utc="2026-11-24T00:00:00Z"))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(solar_disc(request_payload))))
    assert parsed.status == "READY", parsed.issues
    assert parsed.spec.data_source == "coordinate" and parsed.spec.search_step_minutes == 80


def test_too_long_search_is_a_clarification_not_an_engine_error(service, request_payload):
    request_payload["text"] = "Tìm ngày tốt nhất cho Connecting Ridge từ 1/1/2027 đến 1/1/2028 UTC"
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, site_ids=["connecting-ridge"],
        source_quotes=["Tìm ngày tốt nhất"], max_darkness_hours=None,
        search_from_utc="2027-01-01T00:00:00Z", search_until_utc="2028-01-01T00:00:00Z"))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(solar_disc(request_payload))))
    assert parsed.status == "NEEDS_INPUT" and parsed.issues == ["SEARCH_TOO_LARGE"]
    assert "128" in parsed.questions[0].question


def test_catalog_alias_wins_over_model_p1_guess(service, request_payload):
    request_payload["text"] = "so sánh site01 và site04 bắt đầu 2026-11-14T00:00:00Z"
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, arrival_utc="2026-11-14T00:00:00Z",
        site_ids=["Site01_P1", "Site04_P1"], source_quotes=["so sánh site01 và site04"], max_darkness_hours=None))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(solar_disc(request_payload))))
    assert parsed.status == "READY", parsed.issues
    assert parsed.spec.site_ids == ["connecting-ridge", "shackleton-rim"]


def test_literal_p1_ids_are_declined_as_not_tab_sites(service, request_payload):
    request_payload["text"] = "so sánh Site01_P1 và Site04_P1 bắt đầu 2026-11-14T00:00:00Z"
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, arrival_utc="2026-11-14T00:00:00Z",
        site_ids=["Site01_P1", "Site04_P1"], source_quotes=["so sánh Site01_P1 và Site04_P1"], max_darkness_hours=None))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(solar_disc(request_payload))))
    assert parsed.status != "READY" and parsed.issues == ["SITE_NOT_IN_CATALOG"]


def test_three_named_sites_ask_for_two_instead_of_failing(service, request_payload):
    request_payload["text"] = "Compare Shackleton Rim, Malapert Massif and Haworth starting 2026-12-03T00:00:00Z for 72 hours"
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, arrival_utc="2026-12-03T00:00:00Z",
        site_ids=["shackleton-rim", "malapert-massif", "haworth"], source_quotes=["Compare Shackleton Rim"],
        max_darkness_hours=None))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(solar_disc(request_payload))))
    assert parsed.status == "NEEDS_INPUT" and parsed.issues == ["TOO_MANY_SITES"]


def test_explanation_rows_carry_site_display_names(service, request_payload):
    request_payload["text"] = "so sánh site01 và site04 bắt đầu 2026-11-14T00:00:00Z"
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, arrival_utc="2026-11-14T00:00:00Z",
        site_ids=["connecting-ridge", "shackleton-rim"], source_quotes=["so sánh site01 và site04"], max_darkness_hours=None))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(solar_disc(request_payload))))
    result = asyncio.run(service.evaluate(EvaluateRequest(draft_id=parsed.draft_id, spec_hash=parsed.spec_hash,
        baseline=request_payload["baseline"], confirmed=True)))
    rows = json.loads(explain_messages(result.evidence, natural=True)[1]["content"])["candidates"]
    assert {row["site_name"] for row in rows} == {"Connecting Ridge", "Shackleton Rim"}


@pytest.mark.parametrize("answers,expected", [
    (["December 1, 2026", "noon UTC"], "2026-12-01T12:00:00Z"),
    (["December 1, 2026", "midnight UTC"], "2026-12-01T00:00:00Z"),
    (["1 tháng 12 năm 2026", "1 giờ chiều UTC"], "2026-12-01T13:00:00Z"),
    (["1 tháng 12 năm 2026", "8h tối UTC"], "2026-12-01T20:00:00Z"),
    (["1 tháng 12 năm 2026", "9 giờ sáng UTC"], "2026-12-01T09:00:00Z"),
    (["ngày 3/12/2026 lúc 1 giờ chiều UTC"], "2026-12-03T13:00:00Z"),
])
def test_named_and_vietnamese_times_complete_the_start(answers, expected, request_payload):
    request_payload.update(text="Explore Malapert Massif", clarifications=[
        {"question": "When should the mission start?", "answer": answer} for answer in answers])
    context = start_context(ParseRequest.model_validate(request_payload))
    assert context["missing_fields"] == [] and context["arrival_utc"] == expected


def contact_case(service, request_payload, **patch):
    request_payload["text"] = ("hãy tìm thời điểm tốt nhất cho điểm connecting ridge tại 26/11/2026 00:00 UTC "
                               "trong 72 giờ với thời lượng liên lạc 70 phút")
    service.llm = FixtureLLM(default_patch(**{"arrival_shift_days": None, "arrival_utc": "2026-11-26T00:00:00Z",
        "duration_hours": 72.0, "site_ids": ["connecting-ridge"], "source_quotes": ["thời lượng liên lạc 70 phút"],
        "max_darkness_hours": None, **patch}))
    return asyncio.run(service.parse(ParseRequest.model_validate(solar_disc(request_payload))))


def test_contact_minutes_become_engine_contact_requirements(service, request_payload):
    parsed = contact_case(service, request_payload, min_contact_minutes=70.0)
    assert parsed.status == "READY", parsed.issues
    assert parsed.spec.contact_requirements.min_contact_minutes == 70
    assert parsed.spec.search_from_utc is None


def test_best_time_with_one_instant_searches_forward_within_budget(service, request_payload):
    parsed = contact_case(service, request_payload, min_contact_minutes=70.0, search_requested=True)
    assert parsed.status == "READY", parsed.issues
    spec = parsed.spec
    assert spec.search_from_utc == "2026-11-26T00:00:00Z"
    assert spec.search_until_utc == "2026-11-27T08:00:00Z"  # 128 starts x 15 min for one site
    assert spec.search_step_minutes == 15


def test_contact_details_without_minutes_ask_for_minutes(service, request_payload):
    parsed = contact_case(service, request_payload, contact_setup_minutes=10.0)
    assert parsed.status == "NEEDS_INPUT" and parsed.issues == ["MISSING_CONTACT_MINUTES"]
    assert "phút" in parsed.questions[0].question


def test_unsupported_part_is_named_instead_of_generic_rephrase(service, request_payload):
    parsed = contact_case(service, request_payload, unsupported_requirements=["nhiệt độ dưới -150 độ C"])
    assert parsed.status == "UNSUPPORTED_REQUIREMENT"
    question = parsed.questions[0].question
    assert "nhiệt độ dưới -150 độ C" in question and "liên lạc" in question
    assert "nêu lại phần cần thay đổi" not in question


def test_contact_failure_is_an_allowed_explanation_reason():
    from types import SimpleNamespace
    from app.assistant.explanations import explanation_options
    candidate = SimpleNamespace(candidate_id="a", issue=None, decision="FAIL",
        constraint_states={"min_sunlit_fraction": "PASS", "contact.min_contact_minutes": "FAIL"})
    facts = {f"a.{s}": {"candidate_id": "a"} for s in ("sun", "earth", "contact", "dark")}
    assert explanation_options(candidate, facts) == {"CONTACT": "a.contact"}


def test_contact_requirements_carry_to_follow_ups(service, request_payload):
    parsed = contact_case(service, request_payload, min_contact_minutes=70.0)
    request_payload["baseline"]["contact_requirements"] = parsed.spec.contact_requirements.model_dump()
    request_payload["text"] = "lùi 1 ngày, thời gian thiết lập 10 phút"
    service.llm = FixtureLLM(default_patch(arrival_shift_days=1, site_ids=["connecting-ridge"], duration_hours=72.0,
        source_quotes=["lùi 1 ngày"], contact_setup_minutes=10.0, max_darkness_hours=None))
    follow = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    assert follow.status == "READY", follow.issues
    assert follow.spec.contact_requirements.min_contact_minutes == 70
    assert follow.spec.contact_requirements.setup_minutes == 10


def tab_baseline(payload):
    """Baseline the UI now builds from the tabs' shared mission settings."""
    payload["baseline"].update(illumination_model="solar_disc", hardware={"sun_panel": 20.0, "earth_antenna": 20.0},
        min_sunlit_fraction=0.8, min_earth_los_fraction=None,
        contact_requirements={"min_contact_minutes": 30, "setup_minutes": 5, "required_windows": 1,
                              "first_contact_deadline_minutes": 120})
    return payload


def test_tab_settings_baseline_is_accepted_and_kept(service, request_payload):
    request_payload["text"] = "phân tích connecting ridge bắt đầu 2026-11-26T00:00:00Z trong 72 giờ"
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, arrival_utc="2026-11-26T00:00:00Z",
        site_ids=["connecting-ridge"], source_quotes=["phân tích connecting ridge"], max_darkness_hours=None))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(tab_baseline(request_payload))))
    assert parsed.status == "READY", parsed.issues
    assert parsed.spec.hardware.sun_panel == 20 and parsed.spec.hardware.earth_antenna == 20
    assert parsed.spec.min_earth_los_fraction is None
    assert parsed.spec.contact_requirements.min_contact_minutes == 30


def test_stated_heights_override_the_tab_heights(service, request_payload):
    request_payload["text"] = "phân tích connecting ridge bắt đầu 2026-11-26T00:00:00Z, tấm pin cao 1 m và ăng-ten 2 m"
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, arrival_utc="2026-11-26T00:00:00Z",
        site_ids=["connecting-ridge"], source_quotes=["tấm pin cao 1 m"], max_darkness_hours=None,
        hardware_change=True, panel_height_m=1.0, antenna_height_m=2.0))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(tab_baseline(request_payload))))
    assert parsed.status == "READY", parsed.issues
    assert (parsed.spec.hardware.sun_panel, parsed.spec.hardware.earth_antenna) == (1.0, 2.0)


def test_non_height_equipment_change_stays_unsupported(service, request_payload):
    request_payload["text"] = "phân tích connecting ridge bắt đầu 2026-11-26T00:00:00Z với pin mặt trời hiệu suất cao hơn"
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, arrival_utc="2026-11-26T00:00:00Z",
        site_ids=["connecting-ridge"], source_quotes=["phân tích connecting ridge"], max_darkness_hours=None,
        hardware_change=True))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(tab_baseline(request_payload))))
    assert parsed.status == "UNSUPPORTED_REQUIREMENT"
    assert "chiều cao tấm pin và ăng-ten" in parsed.questions[0].question


@pytest.mark.parametrize("text,expected", [
    ("Site01", ["connecting-ridge"]), ("site 01", ["connecting-ridge"]), ("điểm 01", ["connecting-ridge"]),
    ("điểm 04", ["shackleton-rim"]), ("R04", ["shackleton-rim"]),
    ("so sánh Connecting Ridge và Connecting Ridge Extension", ["connecting-ridge", "connecting-ridge-extension"]),
    ("Shackleton Rim B", ["shackleton-rim-b"]), ("Peak Near Shackleton", ["peak-near-shackleton"]),
    ("IM-1", []), ("Mons Mouton", []),  # not among the 27 tab sites
    ("Leibnitz Beta Plateau (extended boundaries)", ["leibnitz-beta-plateau-extended"]),
    ("Malapert Massif và Malapert Crater 1", ["malapert-massif", "malapert-crater-1"]),
    ("Shoemaker Rim A", ["shoemaker-rim-a"]), ("Amundsen Rim và Amundsen 1", ["amundsen-rim", "amundsen-1"]),
])
def test_confusable_site_names_resolve_to_one_point_each(text, expected):
    from app.assistant.sites import named_sites
    assert named_sites(text) == expected


def test_site_labels_distinguish_same_region_and_same_coordinates():
    from app.assistant.sites import site_info
    centre, p1 = site_info("connecting-ridge"), site_info("Site01_P1")
    assert centre["kind"] == "region_centre" and p1["kind"] == "p1_observer"
    assert centre["label"] != p1["label"] and "Connecting Ridge" in p1["label"] and "°S" in p1["label"]
    assert site_info("leibnitz-beta-plateau")["same_coordinates_as"] == ["leibnitz-beta-plateau-extended"]


def test_ready_parse_returns_site_labels_for_review(service, request_payload):
    parsed = contact_case(service, request_payload, min_contact_minutes=70.0)
    assert parsed.site_labels == {"connecting-ridge": "Connecting Ridge (89.4632°S 137.4900°W)"}


def test_qualitative_view_keeps_achieved_vs_required_margin():
    summary = {"result_id": "r1", "status": "NO_FEASIBLE_IN_EVALUATED_SET",
               "request": {"duration_hours": 72, "min_sunlit_fraction": 0.8, "min_earth_los_fraction": 0.8},
               "candidates": [{"candidate_id": "a", "site_id": "a", "decision": "FAIL",
                               "metrics": {"total_sun_hours": [43.2, 46.8], "total_earth_los_hours": [72, 72]},
                               "constraint_states": {"min_sunlit_fraction": "FAIL", "min_earth_los_fraction": "PASS"}}]}
    view = explanation_view(engine_evidence(summary), "Vì sao điểm này không đạt?")
    assert view["detail_mode"] == "qualitative"
    sun = view["facts"]["r1/a/hard.min_sunlit_fraction"]
    assert sun["required_percent"] == 80 and sun["achieved_percent"] == [60, 65]
    assert view["facts"]["r1/a/hard.min_earth_los_fraction"]["achieved_percent"] == 100
    assert "bounds_hours" not in view["facts"]["r1/a/metric.total_sun_hours"]


def test_search_explanation_reports_how_many_starts_were_tried(service, request_payload):
    request_payload["text"] = "Cho phép đổi ngày hạ cánh trong khoảng 2026-11-17T00:00:00Z đến trước 2026-11-18T00:00:00Z"
    service.llm = FixtureLLM(default_patch(arrival_shift_days=None, source_quotes=["Cho phép đổi ngày"],
        search_from_utc="2026-11-17T00:00:00Z", search_until_utc="2026-11-18T00:00:00Z"))
    parsed = asyncio.run(service.parse(ParseRequest.model_validate(request_payload)))
    result = asyncio.run(service.evaluate(EvaluateRequest(draft_id=parsed.draft_id, spec_hash=parsed.spec_hash,
        baseline=request_payload["baseline"], confirmed=True)))
    payload = json.loads(explain_messages(result.evidence, natural=True, question="tốt nhất?")[1]["content"])
    summary = payload["search_summary"]
    assert summary["start_times_evaluated"] == result.evidence.coverage["candidate_total"]
    assert summary["returned_best_non_overlapping"] == len(result.evidence.candidates)
