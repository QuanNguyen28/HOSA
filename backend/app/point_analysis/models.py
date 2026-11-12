from typing import Annotated, Literal

from pydantic import Field

from app.mission.models import Contract, ContactRequirements, MissionRequest


class PointAnalysisRequest(MissionRequest):
    """Compatibility name for the shared mission request."""


class JobStatus(Contract):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    stage: str
    error_code: str | None = None
    result_url: str | None = None
    preview_url: str | None = None


BoundsPair = Annotated[list[float], Field(min_length=2, max_length=2)]
PointDecision = Literal["PASS", "FAIL", "INDETERMINATE"]


class PointAnalysisResult(Contract):
    result_id: str = Field(pattern="^[0-9a-f]{64}$")
    method_version: str
    created_utc: str
    execution: dict
    evaluation_status: Literal["pending", "complete"] = "complete"
    evaluation_stages: dict = Field(default_factory=dict)
    hard_failure: dict | None = None
    timeline_transport: dict = Field(default_factory=dict)
    request: PointAnalysisRequest
    end_utc: str
    coordinate: dict
    decision: PointDecision | None
    nominal_sampled_decision: PointDecision | None
    requirement_policy: str = "availability-fractions-v1"
    illumination: dict = Field(default_factory=dict)
    constraint_checks: dict[str, PointDecision]
    soft_constraint_checks: dict[str, PointDecision]
    soft_violations: list[dict] = Field(default_factory=list)
    contact_analysis: dict | None = None
    metrics_hours: dict[str, BoundsPair]
    joint_hours: BoundsPair | None = None
    availability_fraction: dict[str, BoundsPair]
    coverage: dict
    validation: dict
    timeline: list[dict]
    events: list[dict]
    horizons: dict[str, list[dict]]
    provenance: dict
    resolution: dict = Field(default_factory=dict)
    warnings: list[str]
