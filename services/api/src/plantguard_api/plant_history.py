from __future__ import annotations

import time
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import Settings, get_settings
from .database import CareEvent, Observation, Photo, Plant, User, get_session
from .dependencies import get_photo_link_signer, get_photo_storage
from .photo_links import PhotoLinkSigner
from .photo_storage import PhotoStorage
from .photo_validation import PhotoValidationError, validate_photo_upload
from .schemas import (
    CareEventCreate,
    CareEventResult,
    ObservationResult,
    PhotoResult,
    PlantCreate,
    PlantHistoryResult,
    PlantResult,
)
from .security import get_current_user

router = APIRouter(prefix="/api/v1/plants", tags=["plants"])


def require_plant(session: Session, plant_id: UUID, owner_id: UUID) -> Plant:
    plant = session.scalar(
        select(Plant).where(Plant.id == plant_id, Plant.owner_id == owner_id)
    )
    if plant is None:
        raise HTTPException(status_code=404, detail="Растение не найдено")
    return plant


def photo_result(
    request: Request,
    photo: Photo,
    signer: PhotoLinkSigner,
    configuration: Settings,
) -> PhotoResult:
    expires = int(time.time()) + configuration.photo_url_ttl_seconds
    signature = signer.sign("GET", photo.storage_key, expires)
    url = request.url_for("download_photo", storage_key=photo.storage_key)
    return PhotoResult(
        id=photo.id,
        storage_key=photo.storage_key,
        original_filename=photo.original_filename,
        media_type=photo.media_type,
        size_bytes=photo.size_bytes,
        checksum_sha256=photo.checksum_sha256,
        read_url=str(url.include_query_params(expires=expires, signature=signature)),
    )


def observation_result(
    request: Request,
    observation: Observation,
    signer: PhotoLinkSigner,
    configuration: Settings,
) -> ObservationResult:
    return ObservationResult(
        id=observation.id,
        plant_id=observation.plant_id,
        description=observation.description,
        humidity_pct=float(observation.humidity_pct)
        if observation.humidity_pct is not None
        else None,
        temperature_c=float(observation.temperature_c)
        if observation.temperature_c is not None
        else None,
        observed_at=observation.observed_at,
        created_at=observation.created_at,
        photos=[
            photo_result(request, photo, signer, configuration)
            for photo in observation.photos
        ],
    )


@router.post("", response_model=PlantResult, status_code=status.HTTP_201_CREATED)
def create_plant(
    payload: PlantCreate,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Plant:
    plant = Plant(owner_id=current_user.id, **payload.model_dump())
    session.add(plant)
    session.commit()
    session.refresh(plant)
    return plant


@router.get("/{plant_id}", response_model=PlantResult)
def get_plant(
    plant_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Plant:
    return require_plant(session, plant_id, current_user.id)


@router.post(
    "/{plant_id}/observations",
    response_model=ObservationResult,
    status_code=status.HTTP_201_CREATED,
)
async def create_observation(
    request: Request,
    plant_id: UUID,
    photo: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    signer: Annotated[PhotoLinkSigner, Depends(get_photo_link_signer)],
    configuration: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[User, Depends(get_current_user)],
    description: Annotated[Optional[str], Form()] = None,
    humidity_pct: Annotated[Optional[float], Form()] = None,
    temperature_c: Annotated[Optional[float], Form()] = None,
    observed_at: Annotated[Optional[datetime], Form()] = None,
) -> ObservationResult:
    require_plant(session, plant_id, current_user.id)
    try:
        validated = await validate_photo_upload(
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

    stored = storage.save(validated.content, validated.media_type)
    observation = Observation(
        plant_id=plant_id,
        description=description,
        humidity_pct=Decimal(str(humidity_pct)) if humidity_pct is not None else None,
        temperature_c=Decimal(str(temperature_c)) if temperature_c is not None else None,
    )
    if observed_at is not None:
        observation.observed_at = observed_at
    observation.photos.append(
        Photo(
            storage_key=stored.storage_key,
            original_filename=photo.filename or "photo",
            media_type=validated.media_type,
            size_bytes=stored.size_bytes,
            checksum_sha256=stored.checksum_sha256,
        )
    )
    session.add(observation)
    try:
        session.commit()
        session.refresh(observation)
    except Exception:
        session.rollback()
        storage.delete(stored.storage_key)
        raise
    return observation_result(request, observation, signer, configuration)


@router.post(
    "/{plant_id}/care-events",
    response_model=CareEventResult,
    status_code=status.HTTP_201_CREATED,
)
def create_care_event(
    plant_id: UUID,
    payload: CareEventCreate,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CareEvent:
    require_plant(session, plant_id, current_user.id)
    values = payload.model_dump(exclude_none=True)
    event = CareEvent(plant_id=plant_id, **values)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.get("/{plant_id}/history", response_model=PlantHistoryResult)
def get_plant_history(
    request: Request,
    plant_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    signer: Annotated[PhotoLinkSigner, Depends(get_photo_link_signer)],
    configuration: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PlantHistoryResult:
    plant = session.scalar(
        select(Plant)
        .where(Plant.id == plant_id, Plant.owner_id == current_user.id)
        .options(selectinload(Plant.observations).selectinload(Observation.photos))
    )
    if plant is None:
        raise HTTPException(status_code=404, detail="Растение не найдено")
    observations = sorted(plant.observations, key=lambda item: item.observed_at, reverse=True)
    care_events = sorted(plant.care_events, key=lambda item: item.performed_at, reverse=True)
    return PlantHistoryResult(
        plant=PlantResult.model_validate(plant),
        observations=[
            observation_result(request, observation, signer, configuration)
            for observation in observations
        ],
        care_events=[CareEventResult.model_validate(event) for event in care_events],
    )
