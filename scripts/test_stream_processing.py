#!/usr/bin/env python3
"""Exercise duplicate and out-of-order environment readings on a real Kafka/ksqlDB stack."""

from __future__ import annotations

import json
import time
from typing import Optional
from uuid import uuid4

from kafka import KafkaConsumer, KafkaProducer

BOOTSTRAP_SERVERS = "kafka:29092"
INPUT_TOPIC = "plant.environment-readings.v1"
SUMMARY_TOPIC = "plant.environment.6h-summary.v1"
ALERT_TOPIC = "plant.alerts.v1"
TIMEOUT_SECONDS = 90
SIX_HOURS_MS = 6 * 60 * 60 * 1000


def reading(event_id: str, plant_id: str, occurred_at: int, humidity: float) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": "plant.environment.recorded",
        "schema_version": 1,
        "occurred_at": occurred_at,
        "plant_id": plant_id,
        "source": "simulator",
        "humidity_pct": humidity,
        "temperature_c": 23.0,
    }


def produce_scenario(plant_id: str) -> None:
    current = int(time.time() * 1000)
    completed_window_start = ((current - 7 * 60 * 60 * 1000) // SIX_HOURS_MS) * SIX_HOURS_MS
    newer_timestamp = completed_window_start + 2 * 60 * 60 * 1000
    late_timestamp = completed_window_start + 60 * 60 * 1000
    duplicate_id = str(uuid4())
    duplicate = reading(duplicate_id, plant_id, newer_timestamp, 50.0)
    late = reading(str(uuid4()), plant_id, late_timestamp, 10.0)

    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        acks="all",
        key_serializer=lambda value: value.encode(),
        value_serializer=lambda value: json.dumps(value, separators=(",", ":")).encode(),
    )
    try:
        producer.send(INPUT_TOPIC, key=plant_id, value=duplicate).get(timeout=15)
        producer.send(INPUT_TOPIC, key=plant_id, value=duplicate).get(timeout=15)
        producer.send(INPUT_TOPIC, key=plant_id, value=late).get(timeout=15)
        producer.flush(timeout=15)
    finally:
        producer.close(timeout=15)


def wait_for_results(plant_id: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    consumer = KafkaConsumer(
        SUMMARY_TOPIC,
        ALERT_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=f"plantguard-stream-test-{uuid4()}",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda value: json.loads(value.decode()) if value else None,
    )
    deadline = time.monotonic() + TIMEOUT_SECONDS
    summary: Optional[dict[str, object]] = None
    alerts: list[dict[str, object]] = []
    try:
        while time.monotonic() < deadline:
            for records in consumer.poll(timeout_ms=1000).values():
                for record in records:
                    value = record.value
                    if not isinstance(value, dict) or value.get("PLANT_ID") != plant_id:
                        continue
                    if record.topic == SUMMARY_TOPIC and value.get("READING_COUNT") == 2:
                        summary = value
                    elif record.topic == ALERT_TOPIC:
                        alerts.append(value)
            if summary is not None and alerts:
                return summary, alerts
    finally:
        consumer.close()
    raise AssertionError(
        f"ksqlDB result timeout: summary={summary!r}, alerts={alerts!r}"
    )


def main() -> None:
    plant_id = str(uuid4())
    produce_scenario(plant_id)
    summary, alerts = wait_for_results(plant_id)

    average = float(summary["AVERAGE_HUMIDITY_PCT"])
    if abs(average - 30.0) > 0.001:
        raise AssertionError(f"duplicate affected the average: {summary}")
    low_alerts = [item for item in alerts if item.get("ALERT_CODE") == "humidity_too_low"]
    if len(low_alerts) != 1:
        raise AssertionError(f"late event did not produce one alert: {alerts}")
    print("[ok] duplicate event counted once")
    print("[ok] late event assigned to its event-time window")
    print("[ok] late event produced the expected alert")


if __name__ == "__main__":
    main()
