from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from plantguard_api.database import Base, OutboxEvent
from plantguard_api.outbox import OutboxPublisher
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


class RecordingProducer:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.messages: list[tuple[str, str, dict[str, object]]] = []

    def publish(self, topic: str, key: str, payload: dict[str, object]) -> None:
        if self.failures:
            self.failures -= 1
            raise ConnectionError("Kafka is temporarily unavailable")
        self.messages.append((topic, key, payload))


def test_failed_event_is_retried_once_and_not_duplicated_after_success():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    event_id = uuid4()
    plant_id = uuid4()
    initial_time = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add(
            OutboxEvent(
                id=event_id,
                topic="plant.observations.v1",
                message_key=str(plant_id),
                payload={"event_id": str(event_id), "plant_id": str(plant_id)},
                available_at=initial_time,
            )
        )
        session.commit()

    producer = RecordingProducer(failures=1)
    publisher = OutboxPublisher(producer)
    with Session(engine) as session:
        assert publisher.publish_batch(session, now=initial_time) == 0
        failed = session.get(OutboxEvent, event_id)
        assert failed is not None
        assert failed.status == "pending"
        assert failed.attempts == 1
        assert failed.last_error == "Kafka is temporarily unavailable"

    retry_time = initial_time + timedelta(seconds=3)
    with Session(engine) as session:
        assert publisher.publish_batch(session, now=retry_time) == 1
        published = session.get(OutboxEvent, event_id)
        assert published is not None
        assert published.status == "published"
        assert published.attempts == 2

    with Session(engine) as session:
        assert publisher.publish_batch(session, now=retry_time + timedelta(seconds=1)) == 0

    assert producer.messages == [
        (
            "plant.observations.v1",
            str(plant_id),
            {"event_id": str(event_id), "plant_id": str(plant_id)},
        )
    ]
