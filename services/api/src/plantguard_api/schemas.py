from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ServiceStatus(str, Enum):
    OK = "ok"


class HealthResponse(BaseModel):
    status: ServiceStatus
    service: str


class ValidationStatus(str, Enum):
    VALIDATED = "validated"


class ObservationValidationResult(BaseModel):
    request_id: UUID
    status: ValidationStatus
    received_at: datetime
    persisted: bool = False
    analysis_started: bool = False
    message: str


class PhotoUploadResult(BaseModel):
    storage_key: str
    media_type: str
    size_bytes: int
    checksum_sha256: str
    width: int
    height: int
    read_url: str
    delete_url: str
    links_expire_at: datetime


class SpeciesStatus(str, Enum):
    UNCONFIRMED = "unconfirmed"
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"


class CareActionType(str, Enum):
    WATERED = "watered"
    FERTILIZED = "fertilized"
    REPOTTED = "repotted"
    MOVED = "moved"
    PRUNED = "pruned"
    TREATED = "treated"
    OTHER = "other"


class PlantCreate(BaseModel):
    nickname: str = Field(min_length=1, max_length=100)
    species_scientific_name: Optional[str] = Field(default=None, max_length=160)
    species_common_name: Optional[str] = Field(default=None, max_length=160)
    species_status: SpeciesStatus = SpeciesStatus.UNCONFIRMED


class PlantResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nickname: str
    species_scientific_name: Optional[str]
    species_common_name: Optional[str]
    species_status: SpeciesStatus
    created_at: datetime
    updated_at: datetime


class PhotoResult(BaseModel):
    id: UUID
    storage_key: str
    original_filename: str
    media_type: str
    size_bytes: int
    checksum_sha256: str
    read_url: str


class ObservationResult(BaseModel):
    id: UUID
    plant_id: UUID
    description: Optional[str]
    humidity_pct: Optional[float]
    temperature_c: Optional[float]
    observed_at: datetime
    created_at: datetime
    photos: list[PhotoResult]


class CareEventCreate(BaseModel):
    action_type: CareActionType
    notes: Optional[str] = Field(default=None, max_length=2000)
    performed_at: Optional[datetime] = None


class CareEventResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plant_id: UUID
    action_type: CareActionType
    notes: Optional[str]
    performed_at: datetime
    created_at: datetime


class PlantHistoryResult(BaseModel):
    plant: PlantResult
    observations: list[ObservationResult]
    care_events: list[CareEventResult]


class SpeciesCandidateResult(BaseModel):
    species_code: str
    scientific_name: str
    common_name: str
    confidence: float = Field(ge=0, le=1)


class IdentificationResult(BaseModel):
    observation_id: UUID
    candidates: list[SpeciesCandidateResult] = Field(min_length=1, max_length=3)
    recognized: bool
    needs_review: bool
    model_version: str


class PlantSpeciesUpdate(BaseModel):
    scientific_name: str = Field(min_length=1, max_length=160)
    common_name: Optional[str] = Field(default=None, max_length=160)


class VisualFindingResult(BaseModel):
    code: str
    confidence: float = Field(ge=0, le=1)


class VisualAnalysisResult(BaseModel):
    observation_id: UUID
    analyzable: bool
    findings: list[VisualFindingResult]
    model_version: str


class TextFindingResult(BaseModel):
    code: str
    confidence: float = Field(ge=0, le=1)


class TextAnalysisResult(BaseModel):
    observation_id: UUID
    analyzable: bool
    findings: list[TextFindingResult]
    model_version: str


class UserCreate(BaseModel):
    email: str = Field(
        min_length=5,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    display_name: str = Field(min_length=1, max_length=100)


class UserResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    created_at: datetime


class UserRegistrationResult(UserResult):
    access_token: str
    token_type: str = "bearer"
