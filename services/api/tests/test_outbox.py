from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from plantguard_api import outbox_worker
from plantguard_api.database import Base, OutboxEvent
from plantguard_api.outbox import KafkaEventProducer, OutboxPublisher
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


def test_kafka_producer_uses_supported_delivery_guarantees(monkeypatch):
    captured: dict[str, object] = {}

    class FakeKafkaProducer:
        def __init__(self, **options: object) -> None:
            captured.update(options)

    monkeypatch.setitem(
        sys.modules, "kafka", SimpleNamespace(KafkaProducer=FakeKafkaProducer)
    )

    KafkaEventProducer("kafka:29092")

    assert captured["acks"] == "all"
    assert captured["retries"] == 10
    assert captured["max_in_flight_requests_per_connection"] == 1
    assert "enable_idempotence" not in captured


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


def test_worker_closes_producer_after_graceful_interrupt(monkeypatch):
    calls: list[object] = []

    class Producer:
        def __init__(self, servers):
            calls.append(("producer", servers))

        def close(self):
            calls.append("closed")

    class Publisher:
        def __init__(self, _producer, batch_size):
            calls.append(("publisher", batch_size))

        def publish_batch(self, _session):
            calls.append("published")
            return 1

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    settings = SimpleNamespace(
        kafka_bootstrap_servers="kafka:29092",
        outbox_batch_size=25,
        outbox_poll_interval_seconds=0.01,
    )
    monkeypatch.setattr(outbox_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(outbox_worker, "KafkaEventProducer", Producer)
    monkeypatch.setattr(outbox_worker, "OutboxPublisher", Publisher)
    monkeypatch.setattr(outbox_worker, "get_engine", lambda: object())
    monkeypatch.setattr(outbox_worker, "Session", lambda _engine: FakeSession())
    monkeypatch.setattr(
        outbox_worker.time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    outbox_worker.main()

    assert calls == [
        ("producer", "kafka:29092"),
        ("publisher", 25),
        "published",
        "closed",
    ]
