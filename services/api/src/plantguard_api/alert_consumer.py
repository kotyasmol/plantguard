"""Persist environment alerts emitted by ksqlDB."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from kafka import KafkaConsumer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Plant, get_engine
from .database.models import PlantAlert
from .events import PlantAlertEvent

logger = logging.getLogger(__name__)


def store_alert(engine: Engine, value: bytes) -> None:
    try:
        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise ValueError("Expected an alert object")
        alert = PlantAlertEvent.model_validate({key.lower(): item for key, item in payload.items()})
        occurred_at = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
            milliseconds=alert.occurred_at
        )
    except (ValueError, OverflowError) as error:
        logger.warning("Skipping invalid alert (%s)", type(error).__name__)
        return
    with Session(engine) as session, session.begin():
        # Keep the parent alive until the insert commits, even during profile deletion.
        plant = select(Plant.id).where(Plant.id == alert.plant_id).with_for_update(
            read=True, key_share=True
        )
        if session.scalar(plant) is None:
            return
        statement = insert(PlantAlert).values(
            plant_id=alert.plant_id,
            event_id=alert.event_id,
            alert_code=alert.alert_code,
            severity=alert.severity,
            occurred_at=occurred_at,
        )
        session.execute(statement.on_conflict_do_nothing(index_elements=[PlantAlert.event_id]))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    engine = get_engine()
    consumer = KafkaConsumer(
        "plant.alerts.v1",
        bootstrap_servers=get_settings().kafka_bootstrap_servers,
        group_id="plantguard-alert-storage-v1",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    try:
        while True:
            for records in consumer.poll(timeout_ms=1000, max_records=1).values():
                for record in records:
                    if record.value is not None:
                        store_alert(engine, record.value)
                    consumer.commit()
    except KeyboardInterrupt:
        logger.info("Alert consumer stopped")
    finally:
        consumer.close(autocommit=False)


if __name__ == "__main__":
    main()
