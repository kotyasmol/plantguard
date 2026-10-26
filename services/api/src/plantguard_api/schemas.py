from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


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
