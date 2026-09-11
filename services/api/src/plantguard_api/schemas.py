from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ServiceStatus(str, Enum):
    OK = "ok"


class HealthResponse(BaseModel):
    status: ServiceStatus
    service: str


class ObservationStatus(str, Enum):
    QUEUED = "queued"


class ObservationCreated(BaseModel):
    observation_id: UUID
    status: ObservationStatus
    received_at: datetime
    message: str
