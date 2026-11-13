"""Resolve the proposed language patch against a baseline and immutable capabilities."""
from datetime import timedelta
import re
import unicodedata

from app.core.errors import DomainError
from app.mission.models import MissionRequest
from app.mission.targets import compare_sites
from app.planning.service import start_index
from app.planning.repository import digest
from .models import ContactRequirements, ParseRequest, RequestPatch, RequestSpec, utc
from .provider import AssistantError
from .sites import canonical_site_id, chat_site_ids, excluded_named_sites, named_sites, resolve_coordinates


def _plain(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn').replace('đ', 'd')


def _duration_specified(request):
    """Only current user words can authorize carrying a custom duration forward."""
    texts = [request.text, *(turn.answer for turn in request.clarifications)]
    amount = r'\d+(?:[.,]\d+)?\s*(?:gio|ngay|tuan|thang|nam|hours?|days?|weeks?|months?|years?|h)\b'
    for text in texts:
        plain = _plain(text)
        if (re.search(r'\b(?:trong|keo dai|dai|nhiem vu|thoi luong(?: la)?|for|lasting|duration(?: of)?)\s+' + amount, plain)
                or re.fullmatch(r'\s*' + amount + r'\s*[.!]?\s*', plain)):
            return True
        if re.search(r'\b(?:giu(?: nguyen)?|khong doi)\s+(?:thoi luong|do dai nhiem vu)\b|'
                     r'\b(?:keep|retain)\s+(?:the\s+)?(?:same\s+|current\s+)?duration\b|'
                     r'\b(?:same duration|nhiem vu dai nhu cu)\b', plain):
            return True
    for turn in request.clarifications:
        if re.search(r'thoi luong|keo dai|bao nhieu gio|duration|how long', _plain(turn.question)):
            if re.fullmatch(r'\s*(?:\d+(?:[.,]\d+)?|giu nguyen|nhu cu|yes|same)\s*[.!]?\s*', _plain(turn.answer)):
                return True
    return False


SEARCH_EVALUATION_BUDGET = 128  # Same cap as PlanningService.search.


def search_step_minutes(search_from: str, search_until: str, targets: int, requested: int | None = None,
                        minimum: int = 15) -> int:
    """Smallest 5-minute-grid step that divides the range and fits the engine budget.

    A requested step is honoured exactly; it is never silently coarsened.
    """
    elapsed = (utc(search_until) - utc(search_from)).total_seconds() / 60
    if elapsed <= 0 or elapsed % 5:
        raise AssistantError("INVALID_SEARCH_RANGE")
    elapsed = int(elapsed)
    per_target = SEARCH_EVALUATION_BUDGET // max(1, targets)
    if requested is not None:
        if requested % 5 or elapsed % requested:
            raise AssistantError("INVALID_SEARCH_STEP")
        if elapsed // requested > per_target:
            raise AssistantError("SEARCH_TOO_LARGE")
        return requested
    for step in range(minimum, 1441, 5):
        if elapsed % step == 0 and elapsed // step <= per_target:
            return step
    raise AssistantError("SEARCH_TOO_LARGE")


CONTACT_FIELDS = {"min_contact_minutes": "min_contact_minutes", "contact_setup_minutes": "setup_minutes",
                  "required_contact_windows": "required_windows",
                  "first_contact_deadline_minutes": "first_contact_deadline_minutes"}


def contact_requirements(previous: ContactRequirements | None, patch: RequestPatch) -> ContactRequirements | None:
    """Merge newly stated contact requirements over the working baseline's."""
    updates = {target: getattr(patch, source) for source, target in CONTACT_FIELDS.items()
               if getattr(patch, source) is not None}
    if not updates:
        return previous
    merged = {**(previous.model_dump() if previous else {}), **updates}
    if merged.get("min_contact_minutes") is None:
        # Setup, windows or a deadline only make sense for a minimum contact length.
        raise AssistantError("MISSING_CONTACT_MINUTES")
    return ContactRequirements.model_validate(merged)


def baseline_issue(request: ParseRequest, caps: dict) -> str | None:
    b, scenario = request.baseline, caps["scenario"]
    if b is None:
        return "MISSING_BASELINE"
    if b.scenario_id != scenario["scenario_id"]:
        return "UNSUPPORTED_SCENARIO"
    # Only the legacy centre-visibility snapshot is tied to its precomputed
    # 1 m / 2 m heights; solar-disc planning evaluates any supported height.
    if b.illumination_model == "sun_center" and b.hardware.model_dump() != scenario["device_heights_m"]:
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
    heights = {key: value for key, value in (("sun_panel", patch.panel_height_m), ("earth_antenna", patch.antenna_height_m))
               if value is not None}
    # A hardware change is supported when it is a panel/antenna height; any
    # other equipment change still has to be named as unsupported.
    if (patch.hardware_change and not heights) or patch.unsupported_requirements:
        raise AssistantError("UNSUPPORTED_REQUIREMENT")
    hardware = b.hardware.model_copy(update={key: float(value) for key, value in heights.items()})
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
    # Chat analyses exactly the 27 sites listed in Explore/Compare/Best dates.
    # The archived P1 observers remain reachable only through the legacy
    # centre-visibility snapshot API, which the UI never sends.
    supported = chat_site_ids() | (set(scenario["site_ids"]) if b.illumination_model == "sun_center" else set())
    if b.illumination_model != "sun_center" and any(
            excluded_named_sites(text) for text in (request.text, *(turn.answer for turn in request.clarifications))):
        raise AssistantError("SITE_NOT_IN_CATALOG")
    selected = request.selected_site_ids if request.selected_site_ids is not None else [b.current_site_id]
    named = next(
        (ids for turn in reversed(request.clarifications) if (ids := named_sites(turn.answer))),
        named_sites(request.text),
    )
    if len(named) > 2 or (patch.site_ids and len(patch.site_ids) > 2):
        raise AssistantError("TOO_MANY_SITES")
    explicit = [canonical_site_id(site_id) for site_id in patch.site_ids] if patch.site_ids else None
    if explicit and any(site_id not in supported for site_id in explicit) and not (
            named and len(named) == len(explicit) and not set(named) & set(explicit)):
        # A model guess the user's own words override (handled below) is not an error.
        known = set(coordinate_sites) | set(scenario["site_ids"])
        raise AssistantError("SITE_NOT_IN_CATALOG" if any(s in known for s in explicit if s not in supported)
                             else "UNSUPPORTED_SITE_SCOPE")
    if named and not explicit:
        explicit = named
    elif len(named) == 2 and explicit and set(explicit).issubset(named):
        # Preserve a named comparison if the model left out one target.
        explicit = named
    elif named and explicit and len(explicit) == len(named) and not set(named) & set(explicit):
        # Same number of targets but resolved through a different alias table
        # (e.g. Site01 -> Site01_P1 vs connecting-ridge): the deterministic
        # catalog lookup of the user's own words is authoritative.
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
    if patch.search_requested and search_from is None and search_until is None:
        # "Best time ... at <instant>": search forward from that instant over
        # as many start times as the evaluation budget allows (same as the tab).
        step = patch.search_step_minutes or 15
        slots = SEARCH_EVALUATION_BUDGET // len(selected)
        search_from = at.isoformat().replace("+00:00", "Z")
        search_until = (at + timedelta(minutes=slots * step)).isoformat().replace("+00:00", "Z")
    # All new planning uses the solar-disc model; centre-only snapshots cannot
    # supply that metric even for the original P1 observers and dates.
    coordinate = (b.illumination_model == "solar_disc" or any(s in coordinate_sites for s in selected)
                  or duration != scenario["D_hours"] or patch.mission_end_utc is not None
                  or hardware.model_dump() != scenario["device_heights_m"])
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
        if (at != utc(b.arrival_utc) and b.duration_hours != scenario['D_hours']
                and patch.mission_end_utc is None and not _duration_specified(request)):
            raise AssistantError('DURATION_CONFIRMATION_REQUIRED')
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
    step = None
    if search_from is not None and coordinate:
        step = search_step_minutes(search_from, search_until, len(selected), patch.search_step_minutes)
    elif search_from is not None and patch.search_step_minutes not in (None, scenario["start_step_minutes"]):
        raise AssistantError("OFF_START_GRID")
    constraints = b.constraints.model_copy(update={k: getattr(patch, k) for k in
        ("max_darkness_hours", "max_earth_blackout_hours") if getattr(patch, k) is not None})
    contact = contact_requirements(b.contact_requirements, patch)
    return RequestSpec(
        illumination_model=b.illumination_model,
        resolve_indeterminate=request.resolve_indeterminate,
        scenario_id=b.scenario_id, arrival_utc=arrival,
        end_utc=window.end_utc, duration_hours=window.duration_hours,
        start_index=index, site_ids=selected, hardware=hardware,
        data_source="coordinate" if coordinate else "snapshot",
        constraints=constraints,
        min_sunlit_fraction=patch.min_sunlit_fraction if patch.min_sunlit_fraction is not None else b.min_sunlit_fraction,
        min_earth_los_fraction=patch.min_earth_los_fraction if patch.min_earth_los_fraction is not None else b.min_earth_los_fraction,
        contact_requirements=contact,
        search_from_utc=utc(search_from).isoformat().replace("+00:00", "Z") if search_from else None,
        search_until_utc=utc(search_until).isoformat().replace("+00:00", "Z") if search_until else None,
        search_step_minutes=step,
        rank_by=patch.rank_by or context.rank_by,
        current_site_id=b.current_site_id, baseline_hash=digest(b.model_dump()),
        source_hash=caps["coordinate_source_hash"] if coordinate else caps["source_hash"],
    )
