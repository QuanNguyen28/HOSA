from typing import Annotated, Literal
from pydantic import Field, field_validator

from app.planning.models import (Candidate, ContactRequirements, Contract, Constraints, Decision, Fraction, Hardware,
                                 Hours, RankMetric, RankRange, Status, utc)


class Baseline(Contract):
    illumination_model: Literal["solar_disc", "sun_center"] = "solar_disc"
    scenario_id: str
    arrival_utc: str
    duration_hours: Annotated[float, Field(strict=True, gt=0)]
    hardware: Hardware
    constraints: Constraints
    min_sunlit_fraction: Fraction
    min_earth_los_fraction: Fraction | None = None  # tabs use contact requirements instead
    current_site_id: str
    contact_requirements: ContactRequirements | None = None

    @field_validator("arrival_utc")
    @classmethod
    def aware_time(cls, value: str) -> str:
        utc(value)
        return value


class ClarificationTurn(Contract):
    question: str = Field(min_length=1, max_length=1200)
    answer: str = Field(min_length=1, max_length=1500)


class ClarificationQuestion(Contract):
    field: Literal["arrival_utc", "year", "time", "timezone", "search_range", "site_scope", "mission_duration", "constraints", "request"]
    question: str = Field(min_length=1, max_length=600)


class SiteCoordinates(Contract):
    lat_deg: float = Field(ge=-90, le=90)
    lon_e_deg: float = Field(ge=-180, le=360)


class PlanningContext(Contract):
    rank_by: RankMetric = "total_earth_los_hours"
    search_from_utc: str | None = None
    search_until_utc: str | None = None


class ConversationTurn(Contract):
    text: str = Field(min_length=1, max_length=4000)
    clarifications: list[ClarificationTurn] = Field(default_factory=list, max_length=6)
    outcome: Literal["evaluated", "cancelled", "abandoned"]
    summary: str = Field(default="", max_length=1500)


class ParseRequest(Contract):
    resolve_indeterminate: bool = Field(default=False, strict=True)
    text: str = Field(min_length=1, max_length=4000)
    baseline: Baseline | None = None
    require_explicit_start: bool = False
    selected_site_ids: list[str] | None = Field(default=None, max_length=2)
    clarifications: list[ClarificationTurn] = Field(default_factory=list, max_length=6)
    conversation_history: list[ConversationTurn] = Field(default_factory=list, max_length=8)
    planning_context: PlanningContext = Field(default_factory=PlanningContext)

    @field_validator("text")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Prompt cannot be blank")
        return value


class RequestPatch(Contract):
    response_language: Literal["en", "vi"] | None = None
    arrival_shift_days: Annotated[int, Field(strict=True)] | None
    arrival_utc: str | None
    duration_hours: Annotated[float, Field(strict=True, gt=0)] | None
    mission_end_utc: str | None = None
    hardware_change: bool = Field(strict=True)
    # Equipment heights in metres, as in the Explore/Compare mission settings.
    panel_height_m: Annotated[float, Field(gt=0, le=30)] | None = None
    antenna_height_m: Annotated[float, Field(gt=0, le=30)] | None = None
    site_scope: Literal["selected", "keep_current", "unspecified"]
    # Up to six so a request naming too many sites still parses; normalization
    # then asks the user to choose two instead of the model failing validation.
    site_ids: list[str] | None = Field(default=None, min_length=1, max_length=6)
    site_coordinates: SiteCoordinates | None = None
    max_darkness_hours: Hours | None
    max_earth_blackout_hours: Hours | None
    min_sunlit_fraction: Annotated[float, Field(strict=True, ge=0, le=1)] | None
    min_earth_los_fraction: Fraction | None = None
    # Hard Earth-contact requirements (engine contact_requirements).
    min_contact_minutes: Annotated[float, Field(gt=0)] | None = None
    contact_setup_minutes: Annotated[float, Field(ge=0)] | None = None
    required_contact_windows: Annotated[int, Field(strict=True, ge=1)] | None = None
    first_contact_deadline_minutes: Annotated[float, Field(ge=0)] | None = None
    # Best start-time search requested with only a starting instant.
    search_requested: bool = False
    search_from_utc: str | None = None
    search_until_utc: str | None = None
    search_step_minutes: Annotated[int, Field(strict=True, ge=5, le=1440)] | None = None
    rank_by: RankMetric | None = None
    unresolved_fields: list[str] = Field(max_length=12)
    unsupported_requirements: list[str] = Field(max_length=12)
    source_quotes: list[str] = Field(min_length=1, max_length=12)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list, max_length=3)


class RequestSpec(Contract):
    illumination_model: Literal["solar_disc", "sun_center"] = "solar_disc"
    resolve_indeterminate: bool = Field(default=False, strict=True)
    schema_version: Literal["2.0"] = "2.0"
    scenario_id: str
    arrival_utc: str
    end_utc: str
    start_index: int | None
    duration_hours: float = 72
    data_source: Literal["snapshot", "coordinate"] = "snapshot"
    site_ids: list[str]
    hardware: Hardware
    constraints: Constraints
    min_sunlit_fraction: Fraction
    min_earth_los_fraction: Fraction | None = None
    contact_requirements: ContactRequirements | None = None
    current_site_id: str
    baseline_hash: str
    source_hash: str
    search_from_utc: str | None = None
    search_until_utc: str | None = None
    search_step_minutes: int | None = None
    rank_by: RankMetric = "total_earth_los_hours"


class ParseResponse(Contract):
    status: Literal["READY", "NEEDS_INPUT", "UNSUPPORTED_REQUIREMENT"]
    issues: list[str]
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    patch: RequestPatch | None = None
    draft_id: str | None = None
    spec_hash: str | None = None
    baseline_hash: str | None = None
    spec: RequestSpec | None = None
    # Unambiguous name + coordinates for each selected site, for the Review card.
    site_labels: dict[str, str] = Field(default_factory=dict)
    llm_calls: int


class EvaluateRequest(Contract):
    draft_id: str = Field(pattern="^[0-9a-f]{32}$")
    spec_hash: str = Field(pattern="^[0-9a-f]{64}$")
    baseline: Baseline
    confirmed: bool = Field(strict=True)


class ExplanationBlock(Contract):
    site_id: str
    candidate_id: str | None = None
    reason_code: Literal["DARKNESS", "BLACKOUT", "EARTH_LOS", "SUNLIGHT", "CONTACT", "DATA_MISSING"]
    fact_ids: list[str] = Field(min_length=1, max_length=4)


class ExplainPlan(Contract):
    run_id: str
    spec_hash: str
    lead_code: Status
    blocks: list[ExplanationBlock] = Field(max_length=5)


class NaturalExplanationBlock(ExplanationBlock):
    decision: Decision


class NaturalExplainPlan(ExplainPlan):
    answer: str = Field(min_length=1)
    blocks: list[NaturalExplanationBlock] = Field(max_length=5)


class EvidenceBundle(Contract):
    schema_version: Literal["2.0"] = "2.0"
    run_id: str
    spec_hash: str
    source_hash: str
    request: RequestSpec
    status: Status
    recommended_site_id: str | None
    recommended_candidate_id: str | None = None
    ranking: list[RankRange] = Field(default_factory=list)
    apply_allowed: bool
    coverage: dict[str, int]
    candidates: list[Candidate]
    facts: dict[str, dict]
    warnings: list[str]


class EvaluateResponse(Contract):
    evidence: EvidenceBundle
    explanation_mode: Literal["llm_plan", "llm_failed"]
    explanation: list[str]
    explanation_fact_ids: list[str]
    explanation_error: str | None = None
    llm_calls: int
    model: str
    provider: str | None = None
    trace: list[dict] = Field(default_factory=list)
    prompt_version: str
    token_usage: dict[str, dict | None]
    timings_ms: dict[str, float]
