from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import OutboxEvent


class EventProducer(Protocol):
    def publish(self, topic: str, key: str, payload: dict[str, object]) -> None: ...


def enqueue_event(
    session: Session,
    *,
    topic: str,
    event: BaseModel,
) -> OutboxEvent:
    payload = event.model_dump(mode="json", exclude_none=True)
    queued = OutboxEvent(
        id=UUID(str(payload["event_id"])),
        topic=topic,
        message_key=str(payload["plant_id"]),
        payload=payload,
    )
    session.add(queued)
    return queued


class OutboxPublisher:
    def __init__(self, producer: EventProducer, batch_size: int = 100) -> None:
        self.producer = producer
        self.batch_size = batch_size

    def publish_batch(self, session: Session, now: datetime | None = None) -> int:
        current_time = now or datetime.now(timezone.utc)
        events = session.scalars(
            select(OutboxEvent)
            .where(
                OutboxEvent.status == "pending",
                OutboxEvent.available_at <= current_time,
            )
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .limit(self.batch_size)
            .with_for_update(skip_locked=True)
        ).all()
        published = 0
        for event in events:
            event.attempts += 1
            try:
                self.producer.publish(event.topic, event.message_key, event.payload)
            except Exception as error:
                delay_seconds = min(2**event.attempts, 300)
                event.available_at = current_time + timedelta(seconds=delay_seconds)
                event.last_error = str(error)[:2000]
            else:
                event.status = "published"
                event.published_at = current_time
                event.last_error = None
                published += 1
        session.commit()
        return published


class KafkaEventProducer:
    def __init__(self, bootstrap_servers: str) -> None:
        from kafka import KafkaProducer

        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            acks="all",
            enable_idempotence=True,
            retries=10,
            max_in_flight_requests_per_connection=5,
            key_serializer=lambda value: value.encode(),
            value_serializer=lambda value: json.dumps(
                value, ensure_ascii=False, separators=(",", ":")
            ).encode(),
        )

    def publish(self, topic: str, key: str, payload: dict[str, object]) -> None:
        self.producer.send(topic, key=key, value=payload).get(timeout=15)

    def close(self) -> None:
        self.producer.flush(timeout=15)
        self.producer.close(timeout=15)
