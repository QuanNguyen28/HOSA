from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from app.mission.models import (Contract, Constraints, Hardware, Hours, Fraction, Decision, Status, utc, MissionTarget, MissionRequest, ContactRequirements)

RankMetric = Literal["total_sun_hours", "total_earth_los_hours", "longest_dark_hours", "longest_blackout_hours", "longest_joint_hours"]


class RankRange(Contract):
    candidate_id: str
    rank_min: int
    rank_max: int
    tied_with: list[str]


class Candidate(Contract):
    evaluation_stages: dict = Field(default_factory=dict)
    hard_failure: dict | None = None
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
    sensitivity: dict = Field(default_factory=dict)
    soft_constraint_states: dict[str, Decision] = Field(default_factory=dict)
    soft_violations: list[dict] = Field(default_factory=list)
    nominal_sampled_decision: Decision | None = None
    validation: dict = Field(default_factory=dict)
    contact_analysis: dict | None = None
    coordinate: dict | None = None
    analysis_result_id: str | None = None
    resolution: dict = Field(default_factory=dict)
    illumination: dict = Field(default_factory=dict)



class CompareRequest(Contract):
    evaluation_policy: Literal["hard_first", "complete"] = "hard_first"
    illumination_model: Literal["solar_disc", "sun_center"] = "solar_disc"
    scenario_id: str = "south_pole_demo_v1"
    site_ids: list[str] = Field(default_factory=list, max_length=20)
    targets: list[MissionTarget] = Field(default_factory=list, max_length=20)
    data_source: Literal["snapshot", "coordinate"] = "snapshot"
    arrival_utc: str
    constraints: Constraints = Field(default_factory=Constraints)
    min_sunlit_fraction: Fraction | None = None
    min_earth_los_fraction: Fraction | None = None
    contact_requirements: ContactRequirements | None = None
    offline: bool = False
    resolve_indeterminate: bool = Field(default=False, strict=True)
    hardware: Hardware | None = None
    duration_hours: Annotated[float, Field(strict=True, ge=1)] = 72.0
    end_utc: str | None = None
    current_site_id: str | None = None
    rank_by: RankMetric = "total_earth_los_hours"
    expected_source_hash: str | None = None

    @model_validator(mode="after")
    def mission_contract(self):
        if bool(self.site_ids) == bool(self.targets):
            raise ValueError("Supply either site_ids or targets")
        if self.targets:
            identities = [t.model_dump_json() for t in self.targets]
            if len(set(identities)) != len(identities):
                raise ValueError("Duplicate targets are not allowed")
        if self.min_sunlit_fraction is None and self.min_earth_los_fraction is None and self.contact_requirements is None:
            raise ValueError("Supply min_sunlit_fraction, min_earth_los_fraction or contact_requirements")
        window = {"duration_hours": self.duration_hours} if "duration_hours" in self.model_fields_set or self.end_utc is None else {}
        resolved = MissionRequest(**self.mission_targets()[0].model_dump(), start_utc=self.arrival_utc,
                                 end_utc=self.end_utc, **window)
        self.duration_hours, self.end_utc = resolved.duration_hours, resolved.end_utc
        for target in self.mission_targets():
            self.mission(target)
        return self

    def mission_targets(self):
        return self.targets or [MissionTarget(site_id=site) for site in self.site_ids]

    def mission(self, target, start_utc=None):
        hardware = self.hardware or Hardware(sun_panel=1., earth_antenna=2.)
        return MissionRequest(**target.model_dump(), start_utc=start_utc or self.arrival_utc,
            evaluation_policy=self.evaluation_policy,
            illumination_model=self.illumination_model,
            duration_hours=self.duration_hours, panel_height_m=hardware.sun_panel,
            antenna_height_m=hardware.earth_antenna, min_sunlit_fraction=self.min_sunlit_fraction,
            min_earth_los_fraction=self.min_earth_los_fraction, constraints=self.constraints,
            contact_requirements=self.contact_requirements, offline=self.offline, resolve_indeterminate=self.resolve_indeterminate)

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
    start_step_minutes: int = Field(default=15, strict=True, ge=5, le=1440)

    @field_validator("start_step_minutes")
    @classmethod
    def five_minute_step(cls, value):
        if value % 5:
            raise ValueError("start_step_minutes must be a multiple of 5")
        return value

    @field_validator("until_utc")
    @classmethod
    def aware_end(cls, value: str) -> str:
        utc(value)
        return value


class PlanningResult(Contract):
    schema_version: Literal["2.0"] = "2.0"
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
