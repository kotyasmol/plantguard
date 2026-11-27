from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Plant, User, get_session
from .database.models import PlantAlert
from .schemas import PlantAlertResult
from .security import get_current_user

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def owner_alerts(owner_id: UUID):
    return select(PlantAlert).join(Plant).where(Plant.owner_id == owner_id)


@router.get("", response_model=list[PlantAlertResult])
def list_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    unread: bool = False,
) -> list[PlantAlertResult]:
    query = owner_alerts(current_user.id)
    if unread:
        query = query.where(PlantAlert.acknowledged_at.is_(None))
    alerts = session.scalars(query.order_by(PlantAlert.occurred_at.desc(), PlantAlert.id.desc()))
    return [PlantAlertResult.model_validate(alert) for alert in alerts]


@router.post("/{alert_id}/acknowledge", response_model=PlantAlertResult)
def acknowledge_alert(
    alert_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> PlantAlertResult:
    query = owner_alerts(current_user.id).where(PlantAlert.id == alert_id)
    alert = session.scalar(query.with_for_update(of=PlantAlert))
    if alert is None:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    if alert.acknowledged_at is None:
        alert.acknowledged_at = datetime.now(timezone.utc)
    session.flush()
    session.refresh(alert)
    result = PlantAlertResult.model_validate(alert)
    session.commit()
    return result
