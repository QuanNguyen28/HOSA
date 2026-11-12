"""Resolve the proposed language patch against a baseline and immutable capabilities."""
from datetime import timedelta

from app.core.errors import DomainError
from app.mission.models import MissionRequest
from app.mission.targets import compare_sites
from app.planning.service import start_index
from app.planning.repository import digest
from .models import ParseRequest, RequestPatch, RequestSpec, utc
from .provider import AssistantError
from .sites import canonical_site_id, named_sites, resolve_coordinates


def baseline_issue(request: ParseRequest, caps: dict) -> str | None:
    b, scenario = request.baseline, caps["scenario"]
    if b is None:
        return "MISSING_BASELINE"
    if b.scenario_id != scenario["scenario_id"]:
        return "UNSUPPORTED_SCENARIO"
    if b.hardware.model_dump() != scenario["device_heights_m"]:
        return "UNSUPPORTED_BASELINE_CONFIG"
    coordinate_sites = compare_sites()
    is_coordinate = b.current_site_id in coordinate_sites or any(s in coordinate_sites for s in request.selected_site_ids or [])
    if b.current_site_id not in scenario["site_ids"] and b.current_site_id not in coordinate_sites:
        return "UNSUPPORTED_BASELINE_SITE"
    try:
        MissionRequest(site_id=b.current_site_id, start_utc=b.arrival_utc, duration_hours=b.duration_hours)
        if not is_coordinate and b.duration_hours == scenario["D_hours"]:
            start_index(b.arrival_utc, scenario)
    except (ValueError, DomainError):
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
    duration = patch.duration_hours if patch.duration_hours is not None else b.duration_hours
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
        if request.require_explicit_start:
            raise AssistantError("UNRESOLVED_ARRIVAL")
        search_from, search_until = context.search_from_utc, context.search_until_utc
    coordinate_sites = compare_sites()
    supported = {*scenario["site_ids"], *coordinate_sites}
    selected = request.selected_site_ids if request.selected_site_ids is not None else [b.current_site_id]
    named = next(
        (ids for turn in reversed(request.clarifications) if (ids := named_sites(turn.answer))),
        named_sites(request.text),
    )
    if len(named) > 2:
        raise AssistantError("TOO_MANY_SITES")
    explicit = [canonical_site_id(site_id) for site_id in patch.site_ids] if patch.site_ids else None
    if explicit and any(site_id not in supported for site_id in explicit):
        raise AssistantError("UNSUPPORTED_SITE_SCOPE")
    if named and not explicit:
        explicit = named
    elif len(named) == 2 and explicit and set(explicit).issubset(named):
        # Preserve a named comparison if the model left out one target.
        explicit = named
    elif named and not set(named).issubset(explicit or []):
        raise AssistantError("AMBIGUOUS_SITE_SELECTION")
    if patch.site_scope == "keep_current":
        selected = [b.current_site_id]
    elif patch.site_scope == "selected" and explicit is None and patch.site_coordinates is None:
        if not request.selected_site_ids:
            raise AssistantError("MISSING_REGION")
        selected = request.selected_site_ids
    if patch.site_coordinates is not None:
        coordinate_site = [resolve_coordinates(patch.site_coordinates)]
        if explicit is not None and explicit != coordinate_site:
            raise AssistantError("AMBIGUOUS_SITE_SELECTION")
        explicit = coordinate_site
    if explicit is not None:
        if patch.site_scope == "keep_current" and explicit != [b.current_site_id]:
            raise AssistantError("AMBIGUOUS_SITE_SELECTION")
        selected = explicit
    if not selected or len(set(selected)) != len(selected) or any(s not in supported for s in selected):
        raise AssistantError("UNSUPPORTED_SITE_SCOPE")
    coordinate = any(s in coordinate_sites for s in selected) or duration != scenario["D_hours"] or patch.mission_end_utc is not None
    try:
        if search_from is not None or search_until is not None:
            if search_from is None or search_until is None:
                raise AssistantError("INCOMPLETE_SEARCH_RANGE")
            if coordinate:
                MissionRequest.start_time(search_from)
                MissionRequest.start_time(search_until)
            else:
                start_index(search_from, scenario)
                start_index(search_until, scenario, allow_stop=True)
            if utc(search_until) <= utc(search_from):
                raise AssistantError("INVALID_SEARCH_RANGE")
            if (patch.arrival_shift_days is not None or patch.arrival_utc is not None) and not utc(search_from) <= at < utc(search_until):
                raise AssistantError("AMBIGUOUS_ARRIVAL")
            at = utc(search_from)
        arrival = at.isoformat().replace("+00:00", "Z")
        if coordinate:
            MissionRequest.start_time(arrival)
        index = None if coordinate else start_index(arrival, scenario)
    except DomainError as error:
        raise AssistantError(error.code, error.status_code) from error
    except ValueError as error:
        code = "UNRESOLVED_SEARCH_RANGE" if search_from or search_until else "INVALID_COORDINATE_ARRIVAL"
        raise AssistantError(code) from error
    try:
        duration_input = {"duration_hours": duration} if patch.mission_end_utc is None or patch.duration_hours is not None else {}
        window = MissionRequest(site_id=b.current_site_id, start_utc=arrival, end_utc=patch.mission_end_utc, **duration_input)
    except ValueError as error:
        raise AssistantError("UNSUPPORTED_DURATION") from error
    constraints = b.constraints.model_copy(update={k: getattr(patch, k) for k in
        ("max_darkness_hours", "max_earth_blackout_hours") if getattr(patch, k) is not None})
    return RequestSpec(
        resolve_indeterminate=request.resolve_indeterminate,
        scenario_id=b.scenario_id, arrival_utc=arrival,
        end_utc=window.end_utc, duration_hours=window.duration_hours,
        start_index=index, site_ids=selected, hardware=b.hardware,
        data_source="coordinate" if coordinate else "snapshot",
        constraints=constraints,
        min_sunlit_fraction=patch.min_sunlit_fraction if patch.min_sunlit_fraction is not None else b.min_sunlit_fraction,
        min_earth_los_fraction=patch.min_earth_los_fraction if patch.min_earth_los_fraction is not None else b.min_earth_los_fraction,
        search_from_utc=utc(search_from).isoformat().replace("+00:00", "Z") if search_from else None,
        search_until_utc=utc(search_until).isoformat().replace("+00:00", "Z") if search_until else None,
        rank_by=patch.rank_by or context.rank_by,
        current_site_id=b.current_site_id, baseline_hash=digest(b.model_dump()),
        source_hash=caps["coordinate_source_hash"] if coordinate else caps["source_hash"],
    )
