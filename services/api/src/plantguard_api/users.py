from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Observation, OutboxEvent, Photo, Plant, User, get_session
from .dependencies import get_photo_storage
from .photo_storage import PhotoNotFoundError, PhotoStorage
from .schemas import UserCreate, UserRegistrationResult, UserResult
from .security import generate_access_token, get_current_user, hash_access_token

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("", response_model=UserRegistrationResult, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserCreate,
    session: Annotated[Session, Depends(get_session)],
) -> UserRegistrationResult:
    access_token = generate_access_token()
    user = User(
        email=payload.email.lower(),
        display_name=payload.display_name,
        token_hash=hash_access_token(access_token),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Пользователь уже существует") from error
    session.refresh(user)
    return UserRegistrationResult(
        **UserResult.model_validate(user).model_dump(),
        access_token=access_token,
    )


@router.get("/me", response_model=UserResult)
def get_profile(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> Response:
    plant_ids = list(
        session.scalars(select(Plant.id).where(Plant.owner_id == current_user.id)).all()
    )
    storage_keys = session.scalars(
        select(Photo.storage_key)
        .join(Observation, Photo.observation_id == Observation.id)
        .join(Plant, Observation.plant_id == Plant.id)
        .where(Plant.owner_id == current_user.id)
    ).all()
    for storage_key in storage_keys:
        try:
            storage.delete(storage_key)
        except PhotoNotFoundError:
            pass
    if plant_ids:
        session.execute(
            delete(OutboxEvent).where(
                OutboxEvent.message_key.in_([str(plant_id) for plant_id in plant_ids])
            )
        )
    session.delete(current_user)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
