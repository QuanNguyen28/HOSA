from datetime import datetime, timezone, timedelta
import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Hours = Annotated[float, Field(strict=True, ge=0)]
Fraction = Annotated[float, Field(strict=True, ge=0, le=1)]
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
    """Optional soft preferences; exceeding these never rejects a candidate."""
    max_darkness_hours: Hours | None = Field(default=None, description="Soft preference: maximum continuous darkness, in hours")
    max_earth_blackout_hours: Hours | None = Field(default=None, description="Soft preference: maximum continuous loss of Earth-centre LOS, in hours")


class Hardware(Contract):
    sun_panel: Annotated[float, Field(strict=True, ge=0)]
    earth_antenna: Annotated[float, Field(strict=True, ge=0)]


class MissionTarget(Contract):
    site_id: str | None = None
    latitude_deg: float | None = Field(default=None, gt=-90, lt=90)
    longitude_e_deg: float | None = Field(default=None, ge=-180, le=360)

    @field_validator("latitude_deg", "longitude_e_deg", mode="before")
    @classmethod
    def coordinate_number(cls, value):
        if isinstance(value, bool):
            raise ValueError("Coordinates must be numbers, not booleans")
        return value

    @field_validator("longitude_e_deg")
    @classmethod
    def normalize_longitude(cls, value):
        return value % 360 if value is not None else None

    @model_validator(mode="after")
    def exact_target(self):
        has_coordinates = self.latitude_deg is not None or self.longitude_e_deg is not None
        if self.site_id is not None:
            if not self.site_id.strip() or has_coordinates:
                raise ValueError("Supply either a site_id or both coordinates, never both")
        elif self.latitude_deg is None or self.longitude_e_deg is None:
            raise ValueError("Supply a site_id or both latitude_deg and longitude_e_deg")
        return self

    def resolved(self):
        if self.site_id is None:
            return self
        from .targets import coordinates_for_site
        point = coordinates_for_site(self.site_id)
        return type(self).model_validate({**self.model_dump(exclude={"site_id", "latitude_deg", "longitude_e_deg"}), **point})


class ContactRequirements(Contract):
    min_contact_minutes: float = Field(gt=0, description="Minimum continuous usable Earth-centre LOS after setup")
    setup_minutes: float = Field(default=0.0, ge=0)
    required_windows: int | None = Field(default=None, strict=True, ge=1,
                                        description="Number of distinct qualifying visibility windows, not sessions packed into one window")
    first_contact_deadline_minutes: float | None = Field(default=None, ge=0,
        description="Minutes since mission start by which setup plus one complete qualifying contact must finish")

    @field_validator("min_contact_minutes", "setup_minutes", "first_contact_deadline_minutes", mode="before")
    @classmethod
    def numeric_not_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError("A numeric value is required, not a boolean")
        return value


class MissionRequest(MissionTarget):
    evaluation_policy: Literal["hard_first", "complete"] = Field(default="hard_first",
        description="hard_first stops on a proven sampled hard failure; complete retains all diagnostics for comparison")
    illumination_model: Literal["solar_disc", "sun_center"] = Field(default="solar_disc",
        description="solar_disc: time-mean visible solar-disc area including Earth occultation; sun_center: explicit legacy geometric centre model")
    start_utc: str = Field(description="Timezone-aware ISO 8601 on an exact 5-minute UTC grid",
                           json_schema_extra={"format": "date-time", "examples": ["2026-11-17T00:00:00Z"]})
    duration_hours: float = Field(default=72.0, strict=True, ge=1,
        description="At least 1 hour, in 5-minute increments; no application maximum; may be omitted with end_utc")
    end_utc: str | None = Field(default=None, description="Alternative UTC end date; must agree with duration_hours if both are supplied",
                               json_schema_extra={"format": "date-time"})
    panel_height_m: float = Field(default=1.0, gt=0, le=20)
    antenna_height_m: float = Field(default=2.0, gt=0, le=20)
    constraints: Constraints = Field(default_factory=Constraints)
    min_sunlit_fraction: float | None = Field(default=None, ge=0, le=1,
        description="Minimum time-mean visible solar-disc fraction (0–1) under the default solar_disc model")
    min_earth_los_fraction: float | None = Field(default=None, ge=0, le=1)
    contact_requirements: ContactRequirements | None = None
    offline: bool = False
    resolve_indeterminate: bool = Field(default=False, strict=True, description="Complete missing validation, refine horizon at most twice, and check robust sampled mission paths; full-circle warnings and mission thresholds are retained")

    @field_validator("latitude_deg", "longitude_e_deg", "panel_height_m", "antenna_height_m",
                     "min_sunlit_fraction", "min_earth_los_fraction", mode="before")
    @classmethod
    def numeric_not_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError("A numeric value is required, not a boolean")
        return value

    @field_validator("longitude_e_deg")
    @classmethod
    def east_longitude(cls, value):
        return value % 360 if value is not None else None

    @field_validator("start_utc", "end_utc")
    @classmethod
    def start_time(cls, value):
        if value is None:
            return None
        stamp = utc(value)
        if stamp.minute % 5 or stamp.second or stamp.microsecond:
            raise ValueError("Use an exact 5-minute UTC grid")
        return stamp.isoformat().replace("+00:00", "Z")

    @model_validator(mode="after")
    def stop_time(self):
        if self.end_utc is not None:
            hours = (utc(self.end_utc) - utc(self.start_utc)).total_seconds() / 3600
            if hours < 1:
                raise ValueError("Mission must last at least 1 hour")
            if "duration_hours" in self.model_fields_set and not math.isclose(self.duration_hours, hours, abs_tol=1e-8, rel_tol=0):
                raise ValueError("end_utc and duration_hours describe different mission windows")
            self.duration_hours = hours
        ticks = self.duration_hours * 12
        if not math.isfinite(ticks):
            raise ValueError("Duration must produce a representable UTC end date")
        if not math.isclose(ticks, round(ticks), abs_tol=1e-7, rel_tol=0):
            raise ValueError("Duration must be in exact 5-minute increments")
        self.duration_hours = round(ticks) / 12
        try:
            end = utc(self.start_utc) + timedelta(minutes=round(ticks)*5)
        except (OverflowError, ValueError) as error:
            raise ValueError("Duration must produce a representable UTC end date") from error
        self.end_utc = end.isoformat().replace("+00:00", "Z")
        if (self.contact_requirements is not None
                and self.contact_requirements.first_contact_deadline_minutes is not None
                and self.contact_requirements.first_contact_deadline_minutes > self.duration_hours * 60):
            raise ValueError("First-contact deadline must be within mission duration")
        return self
