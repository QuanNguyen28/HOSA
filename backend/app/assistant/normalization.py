"""Resolve the proposed language patch against a baseline and immutable capabilities."""
from datetime import timedelta

from app.planning.service import start_index
from app.planning.repository import digest
from .models import ParseRequest, RequestPatch, RequestSpec, utc
from .provider import AssistantError
from .sites import resolve_coordinates


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
    for turn in request.conversation_history:
        user_sources.extend([turn.text, *(item.answer for item in turn.clarifications)])
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
    context = request.planning_context
    search_from, search_until = patch.search_from_utc, patch.search_until_utc
    if search_from is None and search_until is None and patch.arrival_shift_days is None and patch.arrival_utc is None:
        search_from, search_until = context.search_from_utc, context.search_until_utc
    if search_from is not None or search_until is not None:
        if search_from is None or search_until is None:
            raise AssistantError("INCOMPLETE_SEARCH_RANGE")
        try:
            first = start_index(search_from, scenario)
            stop = start_index(search_until, scenario, allow_stop=True)
        except ValueError as error:
            raise AssistantError("UNRESOLVED_SEARCH_RANGE") from error
        if stop <= first:
            raise AssistantError("INVALID_SEARCH_RANGE")
        if (patch.arrival_shift_days is not None or patch.arrival_utc is not None) and not utc(search_from) <= at < utc(search_until):
            raise AssistantError("AMBIGUOUS_ARRIVAL")
        at = utc(search_from)
    arrival = at.isoformat().replace("+00:00", "Z")
    index = start_index(arrival, scenario)
    selected = request.selected_site_ids if request.selected_site_ids is not None else [b.current_site_id]
    if patch.site_scope == "keep_current":
        selected = [b.current_site_id]
    elif patch.site_scope == "selected" and patch.site_ids is None and patch.site_coordinates is None:
        if not request.selected_site_ids:
            raise AssistantError("MISSING_REGION")
        selected = request.selected_site_ids
    explicit = patch.site_ids
    if patch.site_coordinates is not None:
        coordinate_site = [resolve_coordinates(patch.site_coordinates)]
        if explicit is not None and explicit != coordinate_site:
            raise AssistantError("AMBIGUOUS_SITE_SELECTION")
        explicit = coordinate_site
    if explicit is not None:
        if patch.site_scope == "keep_current" and explicit != [b.current_site_id]:
            raise AssistantError("AMBIGUOUS_SITE_SELECTION")
        selected = explicit
    if not selected or len(set(selected)) != len(selected) or any(s not in scenario["site_ids"] for s in selected):
        raise AssistantError("UNSUPPORTED_SITE_SCOPE")
    constraints = b.constraints.model_copy(update={k: getattr(patch, k) for k in
        ("max_darkness_hours", "max_earth_blackout_hours") if getattr(patch, k) is not None})
    return RequestSpec(
        scenario_id=b.scenario_id, arrival_utc=arrival,
        end_utc=(at + timedelta(hours=scenario["D_hours"])).isoformat().replace("+00:00", "Z"),
        start_index=index, site_ids=selected, hardware=b.hardware,
        constraints=constraints,
        min_sunlit_fraction=patch.min_sunlit_fraction if patch.min_sunlit_fraction is not None else b.min_sunlit_fraction,
        min_earth_los_fraction=patch.min_earth_los_fraction if patch.min_earth_los_fraction is not None else b.min_earth_los_fraction,
        search_from_utc=utc(search_from).isoformat().replace("+00:00", "Z") if search_from else None,
        search_until_utc=utc(search_until).isoformat().replace("+00:00", "Z") if search_until else None,
        rank_by=patch.rank_by or context.rank_by,
        current_site_id=b.current_site_id, baseline_hash=digest(b.model_dump()), source_hash=caps["source_hash"],
    )
