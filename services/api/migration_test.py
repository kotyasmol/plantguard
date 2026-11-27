"""Exercise the complete Alembic upgrade and downgrade cycle on a test database."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from plantguard_api.config import get_settings
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

EXPECTED_TABLES = {
    "users",
    "plants",
    "observations",
    "photos",
    "care_events",
    "assessments",
    "outbox_events",
    "environment_readings",
    "plant_alerts",
}
EXPECTED_CHECKS = {
    "environment_readings": {
        "ck_environment_readings_has_measurement",
        "ck_environment_readings_humidity_range",
        "ck_environment_readings_temperature_range",
    },
    "plant_alerts": {"ck_plant_alerts_alert_code", "ck_plant_alerts_severity"},
    "plants": {"ck_plants_species_status"},
    "observations": {
        "ck_observations_humidity_range",
        "ck_observations_temperature_range",
    },
    "photos": {"ck_photos_checksum_length", "ck_photos_size_positive"},
    "care_events": {"ck_care_events_action_type"},
    "assessments": {
        "ck_assessments_identification_confidence",
        "ck_assessments_finding_confidence",
        "ck_assessments_risk_level",
        "ck_assessments_status",
    },
    "outbox_events": {
        "ck_outbox_events_attempts_nonnegative",
        "ck_outbox_events_status",
    },
}


def alembic_config() -> Config:
    return Config(str(Path(__file__).with_name("alembic.ini")))


def assert_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing = EXPECTED_TABLES - tables
    if missing:
        raise AssertionError(f"migration did not create: {', '.join(sorted(missing))}")

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "password_hash" not in user_columns:
        raise AssertionError("users is missing password_hash")

    for table, expected_checks in EXPECTED_CHECKS.items():
        checks = {constraint["name"] for constraint in inspector.get_check_constraints(table)}
        if missing_checks := expected_checks - checks:
            raise AssertionError(f"{table} is missing checks: {', '.join(sorted(missing_checks))}")


def assert_cascade_delete(engine: Engine) -> None:
    with engine.begin() as connection:
        user_id = connection.execute(
            text(
                "INSERT INTO users (email, display_name, token_hash) "
                "VALUES ('migration@example.com', 'Migration user', :token_hash) RETURNING id"
            ),
            {"token_hash": "1" * 64},
        ).scalar_one()
        plant_id = connection.execute(
            text(
                "INSERT INTO plants (owner_id, nickname) "
                "VALUES (:owner_id, 'Migration test') RETURNING id"
            ),
            {"owner_id": user_id},
        ).scalar_one()
        observation_id = connection.execute(
            text(
                "INSERT INTO observations (plant_id, humidity_pct) "
                "VALUES (:plant_id, 50) RETURNING id"
            ),
            {"plant_id": plant_id},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO photos "
                "(observation_id, storage_key, original_filename, media_type, size_bytes, "
                "checksum_sha256) VALUES "
                "(:observation_id, 'migration/test.jpg', 'test.jpg', 'image/jpeg', 10, "
                ":checksum)"
            ),
            {"observation_id": observation_id, "checksum": "0" * 64},
        )
        connection.execute(
            text(
                "INSERT INTO assessments (observation_id, status, risk_level) "
                "VALUES (:observation_id, 'pending', 'unknown')"
            ),
            {"observation_id": observation_id},
        )
        connection.execute(
            text("INSERT INTO care_events (plant_id, action_type) VALUES (:plant_id, 'watered')"),
            {"plant_id": plant_id},
        )
        connection.execute(
            text("INSERT INTO environment_readings (plant_id, humidity_pct) VALUES (:plant_id, 8)"),
            {"plant_id": plant_id},
        )
        connection.execute(
            text(
                "INSERT INTO plant_alerts (plant_id, event_id, alert_code, severity, occurred_at) "
                "VALUES (:plant_id, 'migration:environment', 'humidity_too_low', 'critical', now())"
            ),
            {"plant_id": plant_id},
        )
        connection.execute(text("DELETE FROM plants WHERE id = :id"), {"id": plant_id})

        for table in (
            "observations", "photos", "care_events", "assessments",
            "environment_readings", "plant_alerts",
        ):
            remaining = connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            if remaining:
                raise AssertionError(f"cascade delete left rows in {table}")


def main() -> None:
    config = alembic_config()
    engine = create_engine(get_settings().database_url)

    command.upgrade(config, "head")
    assert_schema(engine)
    command.check(config)
    assert_cascade_delete(engine)
    print("[ok] migration upgrade and constraints")

    command.downgrade(config, "0004_user_passwords")
    tables = set(inspect(engine).get_table_names())
    new_tables = {"environment_readings", "plant_alerts"}
    if tables & new_tables or (EXPECTED_TABLES - new_tables) - tables:
        raise AssertionError("migration 0005 did not restore the 0004 schema")
    command.upgrade(config, "head")
    assert_schema(engine)

    engine.dispose()
    command.downgrade(config, "base")
    engine = create_engine(get_settings().database_url)
    remaining = EXPECTED_TABLES & set(inspect(engine).get_table_names())
    if remaining:
        raise AssertionError(f"migration rollback left: {', '.join(sorted(remaining))}")
    print("[ok] migration downgrade")

    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(get_settings().database_url)
    assert_schema(engine)
    print("[ok] migration reapply")
    engine.dispose()


if __name__ == "__main__":
    main()
