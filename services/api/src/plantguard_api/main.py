from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import Settings, get_settings
from .dependencies import get_photo_link_signer, get_photo_storage
from .photo_links import PhotoLinkSigner
from .photo_storage import InvalidStorageKey, PhotoNotFoundError, PhotoStorage
from .photo_validation import PhotoValidationError, validate_photo_upload
from .schemas import (
    HealthResponse,
    ObservationValidationResult,
    PhotoUploadResult,
    ServiceStatus,
    ValidationStatus,
)

application_settings = get_settings()

app = FastAPI(
    title="PlantGuard API",
    version="0.1.0",
    description="Plant observation validation and protected photo storage API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=application_settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["DELETE", "GET", "POST"],
    allow_headers=["Content-Type"],
)


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
    configuration: Annotated[Settings, Depends(get_settings)],
    description: Annotated[str, Form()] = "",
    humidity_pct: Annotated[Optional[float], Form()] = None,
    temperature_c: Annotated[Optional[float], Form()] = None,
) -> ObservationValidationResult:
    try:
        await validate_photo_upload(
            photo,
            max_bytes=configuration.max_image_bytes,
            max_pixels=configuration.max_image_pixels,
        )
    except PhotoValidationError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
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


@app.post(
    "/api/v1/photos",
    response_model=PhotoUploadResult,
    status_code=status.HTTP_201_CREATED,
    tags=["photos"],
)
async def upload_photo(
    request: Request,
    photo: Annotated[UploadFile, File()],
    configuration: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    signer: Annotated[PhotoLinkSigner, Depends(get_photo_link_signer)],
) -> PhotoUploadResult:
    try:
        validated = await validate_photo_upload(
            photo,
            max_bytes=configuration.max_image_bytes,
            max_pixels=configuration.max_image_pixels,
        )
    except PhotoValidationError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error

    stored = storage.save(validated.content, validated.media_type)
    expires = int(time.time()) + configuration.photo_url_ttl_seconds
    read_signature = signer.sign("GET", stored.storage_key, expires)
    delete_signature = signer.sign("DELETE", stored.storage_key, expires)
    read_url = request.url_for("download_photo", storage_key=stored.storage_key)
    delete_url = request.url_for("delete_photo", storage_key=stored.storage_key)

    return PhotoUploadResult(
        storage_key=stored.storage_key,
        media_type=validated.media_type,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
        width=validated.width,
        height=validated.height,
        read_url=str(read_url.include_query_params(expires=expires, signature=read_signature)),
        delete_url=str(
            delete_url.include_query_params(expires=expires, signature=delete_signature)
        ),
        links_expire_at=datetime.fromtimestamp(expires, tz=timezone.utc),
    )


@app.get("/api/v1/photos/{storage_key:path}", name="download_photo", tags=["photos"])
def download_photo(
    storage_key: str,
    expires: int,
    signature: str,
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    signer: Annotated[PhotoLinkSigner, Depends(get_photo_link_signer)],
) -> FileResponse:
    if not signer.verify("GET", storage_key, expires, signature):
        raise HTTPException(status_code=403, detail="Ссылка недействительна или истекла")
    try:
        photo = storage.locate(storage_key)
    except (InvalidStorageKey, PhotoNotFoundError):
        raise HTTPException(status_code=404, detail="Фотография не найдена") from None
    return FileResponse(
        photo.path,
        media_type=photo.media_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.delete(
    "/api/v1/photos/{storage_key:path}",
    name="delete_photo",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["photos"],
)
def delete_photo(
    storage_key: str,
    expires: int,
    signature: str,
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    signer: Annotated[PhotoLinkSigner, Depends(get_photo_link_signer)],
) -> Response:
    if not signer.verify("DELETE", storage_key, expires, signature):
        raise HTTPException(status_code=403, detail="Ссылка недействительна или истекла")
    try:
        storage.delete(storage_key)
    except (InvalidStorageKey, PhotoNotFoundError):
        raise HTTPException(status_code=404, detail="Фотография не найдена") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
