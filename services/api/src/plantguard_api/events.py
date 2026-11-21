from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    schema_version: Literal[1]
    occurred_at: int = Field(ge=0)
    plant_id: UUID


class PlantObservationEvent(StrictEvent):
    event_type: Literal["plant.observation.created"]
    observation_id: UUID
    photo_uri: str
    description: Optional[str] = None
    humidity_pct: Optional[float] = Field(default=None, ge=0, le=100)
    temperature_c: Optional[float] = Field(default=None, ge=-50, le=70)


class EnvironmentReadingEvent(StrictEvent):
    event_type: Literal["plant.environment.recorded"]
    source: Literal["manual", "simulator", "sensor"]
    humidity_pct: Optional[float] = Field(default=None, ge=0, le=100)
    temperature_c: Optional[float] = Field(default=None, ge=-50, le=70)


class PlantAlertEvent(StrictEvent):
    event_type: Literal["plant.environment.alerted"]
    alert_code: Literal[
        "humidity_too_low",
        "humidity_too_high",
        "temperature_too_low",
        "temperature_too_high",
    ]
    severity: Literal["warning", "critical"]


class PlantCareEvent(StrictEvent):
    event_type: Literal["plant.care-event.recorded"]
    care_event_id: UUID
    action_type: Literal[
        "watered", "fertilized", "repotted", "moved", "pruned", "treated", "other"
    ]
    notes: Optional[str] = Field(default=None, max_length=2000)


class IdentificationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scientific_name: str = Field(min_length=1, max_length=160)
    common_name: Optional[str] = Field(default=None, max_length=160)
    confidence: float = Field(ge=0, le=1)


class PlantIdentificationResultEvent(StrictEvent):
    event_type: Literal["plant.identification.completed"]
    observation_id: UUID
    candidates: list[IdentificationCandidate] = Field(min_length=1, max_length=3)
    needs_review: bool
    model_version: str = Field(min_length=1, max_length=120)


class PlantAssessmentResultEvent(StrictEvent):
    event_type: Literal["plant.assessment.completed"]
    assessment_id: UUID
    observation_id: UUID
    status: Literal["succeeded", "needs_review", "failed"]
    risk_level: Literal["unknown", "low", "medium", "high"]
    finding_code: Optional[str] = Field(max_length=80)
    finding_confidence: Optional[float] = Field(ge=0, le=1)
    explanation: Optional[str] = Field(max_length=4000)
    model_version: Optional[str] = Field(max_length=120)


EVENT_MODELS: dict[str, type[StrictEvent]] = {
    "environment-reading.v1.schema.json": EnvironmentReadingEvent,
    "plant-alert.v1.schema.json": PlantAlertEvent,
    "plant-assessment-result.v1.schema.json": PlantAssessmentResultEvent,
    "plant-care-event.v1.schema.json": PlantCareEvent,
    "plant-identification-result.v1.schema.json": PlantIdentificationResultEvent,
    "plant-observation.v1.schema.json": PlantObservationEvent,
}
