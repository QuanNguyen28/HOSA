from typing import Annotated, Literal
from pydantic import Field, field_validator

from app.planning.models import Candidate, Contract, Constraints, Decision, Fraction, Hardware, Hours, RankMetric, RankRange, Status, utc


class Baseline(Contract):
    scenario_id: str
    arrival_utc: str
    duration_hours: Annotated[float, Field(strict=True, gt=0)]
    hardware: Hardware
    constraints: Constraints
    min_sunlit_fraction: Fraction
    min_earth_los_fraction: Fraction
    current_site_id: str

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
    question: str = Field(min_length=1, max_length=300)


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
    text: str = Field(min_length=1, max_length=4000)
    baseline: Baseline | None = None
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
    arrival_shift_days: Annotated[int, Field(strict=True)] | None
    arrival_utc: str | None
    duration_hours: Annotated[float, Field(strict=True, gt=0)] | None
    hardware_change: bool = Field(strict=True)
    site_scope: Literal["selected", "keep_current", "unspecified"]
    site_ids: list[str] | None = Field(default=None, min_length=1, max_length=2)
    site_coordinates: SiteCoordinates | None = None
    max_darkness_hours: Hours | None
    max_earth_blackout_hours: Hours | None
    min_sunlit_fraction: Annotated[float, Field(strict=True, ge=0, le=1)] | None
    min_earth_los_fraction: Fraction | None = None
    search_from_utc: str | None = None
    search_until_utc: str | None = None
    rank_by: RankMetric | None = None
    unresolved_fields: list[str] = Field(max_length=12)
    unsupported_requirements: list[str] = Field(max_length=12)
    source_quotes: list[str] = Field(min_length=1, max_length=12)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list, max_length=3)


class RequestSpec(Contract):
    schema_version: Literal["2.0"] = "2.0"
    scenario_id: str
    arrival_utc: str
    end_utc: str
    start_index: int
    site_ids: list[str]
    hardware: Hardware
    constraints: Constraints
    min_sunlit_fraction: Fraction
    min_earth_los_fraction: Fraction
    current_site_id: str
    baseline_hash: str
    source_hash: str
    search_from_utc: str | None = None
    search_until_utc: str | None = None
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
    llm_calls: int


class EvaluateRequest(Contract):
    draft_id: str = Field(pattern="^[0-9a-f]{32}$")
    spec_hash: str = Field(pattern="^[0-9a-f]{64}$")
    baseline: Baseline
    confirmed: bool = Field(strict=True)


class ExplanationBlock(Contract):
    site_id: str
    candidate_id: str | None = None
    reason_code: Literal["DARKNESS", "BLACKOUT", "EARTH_LOS", "SUNLIGHT", "DATA_MISSING"]
    fact_ids: list[str] = Field(min_length=1, max_length=4)


class ExplainPlan(Contract):
    run_id: str
    spec_hash: str
    lead_code: Status
    blocks: list[ExplanationBlock] = Field(max_length=5)


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
