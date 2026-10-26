from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .schemas import (
    HealthResponse,
    ObservationValidationResult,
    ServiceStatus,
    ValidationStatus,
)

settings = get_settings()

app = FastAPI(
    title="PlantGuard API",
    version="0.1.0",
    description="Input validation prototype for plant observations.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def image_matches_media_type(content: bytes, media_type: str) -> bool:
    signatures = {
        "image/jpeg": content.startswith(b"\xff\xd8\xff"),
        "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    }
    return signatures.get(media_type, False)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status=ServiceStatus.OK, service="plantguard-api")


@app.post(
    "/api/v1/observations/validate",
    response_model=ObservationValidationResult,
    status_code=status.HTTP_200_OK,
    tags=["observations"],
)
async def validate_observation(
    photo: Annotated[UploadFile, File()],
    description: Annotated[str, Form()] = "",
    humidity_pct: Annotated[Optional[float], Form()] = None,
    temperature_c: Annotated[Optional[float], Form()] = None,
) -> ObservationValidationResult:
    if photo.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются изображения JPEG, PNG и WebP",
        )

    content = await photo.read(settings.max_image_bytes + 1)
    if not content:
        raise HTTPException(status_code=422, detail="Файл изображения пуст")
    if len(content) > settings.max_image_bytes:
        raise HTTPException(status_code=413, detail="Файл изображения слишком большой")
    if not image_matches_media_type(content, photo.content_type):
        raise HTTPException(status_code=422, detail="Содержимое файла не соответствует изображению")
    if humidity_pct is not None and not 0 <= humidity_pct <= 100:
        raise HTTPException(status_code=422, detail="Влажность должна быть от 0 до 100")
    if temperature_c is not None and not -50 <= temperature_c <= 70:
        raise HTTPException(
            status_code=422,
            detail="Температура находится вне допустимого диапазона",
        )

    return ObservationValidationResult(
        request_id=uuid4(),
        status=ValidationStatus.VALIDATED,
        received_at=datetime.now(timezone.utc),
        message="Данные прошли проверку; сохранение и анализ пока не подключены",
    )
