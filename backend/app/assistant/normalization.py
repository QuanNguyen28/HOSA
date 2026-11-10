"""Resolve the proposed language patch against a baseline and immutable capabilities."""
from datetime import timedelta

from app.planning.service import start_index
from app.planning.repository import digest
from .models import ParseRequest, RequestPatch, RequestSpec, utc
from .provider import AssistantError


def baseline_issue(request: ParseRequest, caps: dict) -> str | None:
    b, scenario = request.baseline, caps["scenario"]
    if b is None:
        return "MISSING_BASELINE"
    if b.scenario_id != scenario["scenario_id"]:
        return "UNSUPPORTED_SCENARIO"
    if b.duration_hours != scenario["D_hours"] or b.hardware.model_dump() != scenario["device_heights_m"]:
        return "UNSUPPORTED_BASELINE_CONFIG"
    if b.current_site_id not in scenario["site_ids"]:
        return "UNSUPPORTED_BASELINE_SITE"
    try:
        start_index(b.arrival_utc, scenario)
    except (ValueError, AssistantError):
        return "INVALID_BASELINE_TIME"
    return None

def normalize_request(request: ParseRequest, patch: RequestPatch, caps: dict) -> RequestSpec:
    b, scenario = request.baseline, caps["scenario"]
    assert b is not None
    if patch.hardware_change or patch.unsupported_requirements:
        raise AssistantError("UNSUPPORTED_REQUIREMENT")
    if patch.unresolved_fields or patch.clarification_questions:
        raise AssistantError("UNRESOLVED_FIELDS")
    user_sources = [request.text, *(turn.answer for turn in request.clarifications)]
    if any(not q.strip() or not any(q in source for source in user_sources) for q in patch.source_quotes):
        raise AssistantError("UNSUPPORTED_SOURCE_QUOTE")
    if patch.arrival_shift_days is not None and patch.arrival_utc is not None:
        raise AssistantError("AMBIGUOUS_ARRIVAL")
    if patch.duration_hours is not None and patch.duration_hours != scenario["D_hours"]:
        raise AssistantError("UNSUPPORTED_DURATION")
    at = utc(b.arrival_utc)
    if patch.arrival_shift_days is not None:
        try:
            at += timedelta(days=patch.arrival_shift_days)
        except OverflowError as error:
            raise AssistantError("OUTSIDE_TIME_COVERAGE") from error
    if patch.arrival_utc is not None:
        try:
            at = utc(patch.arrival_utc)
        except ValueError as error:
            raise AssistantError("UNRESOLVED_ARRIVAL") from error
    if patch.search_from_utc is not None or patch.search_until_utc is not None:
        if patch.search_from_utc is None or patch.search_until_utc is None:
            raise AssistantError("INCOMPLETE_SEARCH_RANGE")
        try:
            first = start_index(patch.search_from_utc, scenario)
            stop = start_index(patch.search_until_utc, scenario, allow_stop=True)
        except ValueError as error:
            raise AssistantError("UNRESOLVED_SEARCH_RANGE") from error
        if stop <= first:
            raise AssistantError("INVALID_SEARCH_RANGE")
        if (patch.arrival_shift_days is not None or patch.arrival_utc is not None) and not utc(patch.search_from_utc) <= at < utc(patch.search_until_utc):
            raise AssistantError("AMBIGUOUS_ARRIVAL")
        at = utc(patch.search_from_utc)
    arrival = at.isoformat().replace("+00:00", "Z")
    index = start_index(arrival, scenario)
    selected = [b.current_site_id]
    if patch.site_scope == "selected":
        if not request.selected_site_ids:
            raise AssistantError("MISSING_REGION")
        selected = request.selected_site_ids
    if len(set(selected)) != len(selected) or any(s not in scenario["site_ids"] for s in selected):
        raise AssistantError("UNSUPPORTED_SITE_SCOPE")
    constraints = b.constraints.model_copy(update={k: getattr(patch, k) for k in
        ("max_darkness_hours", "max_earth_blackout_hours") if getattr(patch, k) is not None})
    return RequestSpec(
        scenario_id=b.scenario_id, arrival_utc=arrival,
        end_utc=(at + timedelta(hours=scenario["D_hours"])).isoformat().replace("+00:00", "Z"),
        start_index=index, site_ids=selected, hardware=b.hardware,
        constraints=constraints, min_sunlit_fraction=patch.min_sunlit_fraction,
        search_from_utc=utc(patch.search_from_utc).isoformat().replace("+00:00", "Z") if patch.search_from_utc else None,
        search_until_utc=utc(patch.search_until_utc).isoformat().replace("+00:00", "Z") if patch.search_until_utc else None,
        rank_by=patch.rank_by or "longest_dark_hours",
        current_site_id=b.current_site_id, baseline_hash=digest(b.model_dump()), source_hash=caps["source_hash"],
    )
