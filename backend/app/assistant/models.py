from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Hours = Annotated[float, Field(strict=True, ge=0, le=72)]
Decision = Literal["PASS", "FAIL", "INDETERMINATE"]
Status = Literal["FEASIBLE", "NO_FEASIBLE_IN_EVALUATED_SET", "INSUFFICIENT_DATA"]


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("An explicit time zone is required")
    return parsed.astimezone(timezone.utc)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Constraints(Contract):
    max_darkness_hours: Hours
    max_earth_blackout_hours: Hours


class Hardware(Contract):
    sun_panel: Annotated[float, Field(strict=True, ge=0)]
    earth_antenna: Annotated[float, Field(strict=True, ge=0)]


class Baseline(Contract):
    scenario_id: str
    arrival_utc: str
    duration_hours: Annotated[float, Field(strict=True, gt=0)]
    hardware: Hardware
    constraints: Constraints
    current_site_id: str

    @field_validator("arrival_utc")
    @classmethod
    def aware_time(cls, value: str) -> str:
        utc(value)
        return value


class ParseRequest(Contract):
    text: str = Field(min_length=1, max_length=4000)
    baseline: Baseline | None = None
    selected_site_ids: list[str] | None = Field(default=None, max_length=2)

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
    max_darkness_hours: Hours | None
    max_earth_blackout_hours: Hours | None
    min_sunlit_fraction: Annotated[float, Field(strict=True, ge=0, le=1)] | None
    unresolved_fields: list[str] = Field(max_length=12)
    unsupported_requirements: list[str] = Field(max_length=12)
    source_quotes: list[str] = Field(min_length=1, max_length=12)


class RequestSpec(Contract):
    schema_version: Literal["1.0"] = "1.0"
    scenario_id: str
    arrival_utc: str
    end_utc: str
    start_index: int
    site_ids: list[str]
    hardware: Hardware
    constraints: Constraints
    min_sunlit_fraction: float | None
    current_site_id: str
    baseline_hash: str
    source_hash: str


class ParseResponse(Contract):
    status: Literal["READY", "NEEDS_INPUT", "UNSUPPORTED_REQUIREMENT"]
    issues: list[str]
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
    reason_code: Literal["DARKNESS", "EARTH_LOS", "SUNLIGHT", "DATA_MISSING"]
    fact_ids: list[str] = Field(min_length=1, max_length=4)


class ExplainPlan(Contract):
    run_id: str
    spec_hash: str
    lead_code: Status
    blocks: list[ExplanationBlock] = Field(min_length=1, max_length=2)


class Candidate(Contract):
    site_id: str
    decision: Decision
    metrics: dict[str, list[float]]
    constraint_states: dict[str, Decision]
    decisive_event: dict | None
    provenance: dict
    issue: str | None = None


class EvidenceBundle(Contract):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    spec_hash: str
    source_hash: str
    request: RequestSpec
    status: Status
    recommended_site_id: str | None
    apply_allowed: bool
    coverage: dict[str, int]
    candidates: list[Candidate]
    facts: dict[str, dict]
    warnings: list[str]


class EvaluateResponse(Contract):
    evidence: EvidenceBundle
    explanation_mode: Literal["llm_plan", "template_fallback"]
    explanation: list[str]
    explanation_fact_ids: list[str]
    llm_calls: int
    model: str
    prompt_version: str
    token_usage: dict[str, dict | None]
    timings_ms: dict[str, float]
