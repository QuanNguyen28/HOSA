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


RankMetric = Literal["longest_dark_hours", "longest_blackout_hours", "total_sun_hours", "longest_joint_hours"]


class RankRange(Contract):
    candidate_id: str
    rank_min: int
    rank_max: int
    tied_with: list[str]


class Candidate(Contract):
    site_id: str
    decision: Decision
    metrics: dict[str, list[float]]
    constraint_states: dict[str, Decision]
    decisive_event: dict | None
    provenance: dict
    issue: str | None = None
    candidate_id: str | None = None
    start_index: int | None = None
    start_utc: str | None = None
    end_utc: str | None = None
    events: list[dict] = Field(default_factory=list)
    metric_context: dict[str, dict] = Field(default_factory=dict)
    violations: list[dict] = Field(default_factory=list)



class CompareRequest(Contract):
    scenario_id: str
    site_ids: list[str] = Field(min_length=1, max_length=2)
    arrival_utc: str
    constraints: Constraints
    min_sunlit_fraction: Annotated[float, Field(strict=True, ge=0, le=1)] | None = None
    hardware: Hardware | None = None
    duration_hours: Annotated[float, Field(strict=True, gt=0)] = 72
    current_site_id: str | None = None
    rank_by: RankMetric = "longest_dark_hours"
    expected_source_hash: str | None = None

    @field_validator("arrival_utc")
    @classmethod
    def aware_time(cls, value: str) -> str:
        utc(value)
        return value

    @field_validator("site_ids")
    @classmethod
    def unique_sites(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Duplicate sites are not allowed")
        return value


class SearchRequest(CompareRequest):
    until_utc: str
    max_results: Annotated[int, Field(strict=True, ge=1, le=20)] = 5
    non_overlapping: bool = Field(default=True, strict=True)

    @field_validator("until_utc")
    @classmethod
    def aware_end(cls, value: str) -> str:
        utc(value)
        return value


class PlanningResult(Contract):
    schema_version: Literal["1.0"] = "1.0"
    result_id: str
    operation: Literal["compare", "window_search"]
    status: Status
    candidates: list[Candidate]
    recommended_candidate_id: str | None
    apply_allowed: bool
    rank_by: RankMetric
    ranking: list[RankRange]
    coverage: dict[str, int]
    dataset_version: str
    method_version: str
    source_hash: str
    request: dict
    warnings: list[str]
