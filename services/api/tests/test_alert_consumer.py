import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from plantguard_api import alert_consumer
from plantguard_api.database import Base, Plant, User
from plantguard_api.database.models import PlantAlert
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_redelivery_preserves_read_status_and_deleted_plants_are_skipped():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(email="owner@example.com", display_name="Owner", token_hash="a" * 64)
        plant = Plant(nickname="Fern", owner=owner)
        session.add(plant)
        session.commit()
        plant_id = plant.id

    payload = {
        "EVENT_ID": f"{uuid4()}:environment",
        "EVENT_TYPE": "plant.environment.alerted",
        "SCHEMA_VERSION": 1,
        "PLANT_ID": str(plant_id),
        "OCCURRED_AT": 1770000000123,
        "ALERT_CODE": "humidity_too_low",
        "SEVERITY": "critical",
    }
    value = json.dumps(payload).encode()
    alert_consumer.store_alert(engine, value)
    with Session(engine) as session:
        alert = session.scalars(select(PlantAlert)).one()
        assert alert.event_id == payload["EVENT_ID"]
        assert alert.plant_id == plant_id
        assert alert.severity == "critical"
        assert alert.alert_code == "humidity_too_low"
        assert alert.occurred_at.microsecond == 123000
        alert.acknowledged_at = datetime.now(timezone.utc)
        session.commit()
    alert_consumer.store_alert(engine, value)
    payload.update(PLANT_ID=str(uuid4()), EVENT_ID="removed:environment")
    alert_consumer.store_alert(engine, json.dumps(payload).encode())
    with Session(engine) as session:
        assert session.scalars(select(PlantAlert)).one().acknowledged_at is not None
    engine.dispose()


@pytest.mark.parametrize("value", [b"not-json", b"[]", b"{}"])
def test_invalid_alert_skipped_before_database_access(value, caplog):
    alert_consumer.store_alert(None, value)
    assert "Skipping invalid alert" in caplog.text


@pytest.mark.parametrize("fail_storage", [True, False])
def test_worker_commits_only_after_storage(monkeypatch, fail_storage):
    consumer = Mock()
    record = SimpleNamespace(value=b"alert", partition=0, offset=7)
    consumer.poll.side_effect = [{0: [record]}, KeyboardInterrupt()]
    factory = Mock(return_value=consumer)
    monkeypatch.setattr(alert_consumer, "KafkaConsumer", factory)
    monkeypatch.setattr(alert_consumer, "get_engine", lambda: None)

    def store(_engine, value):
        consumer.commit.assert_not_called()
        assert value == record.value
        if fail_storage:
            raise ConnectionError("database unavailable")

    monkeypatch.setattr(alert_consumer, "store_alert", store)
    if fail_storage:
        with pytest.raises(ConnectionError):
            alert_consumer.main()
        consumer.commit.assert_not_called()
    else:
        alert_consumer.main()
        consumer.commit.assert_called_once_with()
    consumer.close.assert_called_once_with(autocommit=False)
    assert factory.call_args.kwargs["enable_auto_commit"] is False
    assert consumer.poll.call_args.kwargs["max_records"] == 1
