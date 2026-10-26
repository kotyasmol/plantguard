"""Exercise the complete Alembic upgrade and downgrade cycle on a test database."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from plantguard_api.config import get_settings
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

EXPECTED_TABLES = {"plants", "observations", "photos", "care_events", "assessments"}
EXPECTED_CHECKS = {
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
}


def alembic_config() -> Config:
    return Config(str(Path(__file__).with_name("alembic.ini")))


def assert_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing = EXPECTED_TABLES - tables
    if missing:
        raise AssertionError(f"migration did not create: {', '.join(sorted(missing))}")

    for table, expected_checks in EXPECTED_CHECKS.items():
        checks = {constraint["name"] for constraint in inspector.get_check_constraints(table)}
        if missing_checks := expected_checks - checks:
            raise AssertionError(f"{table} is missing checks: {', '.join(sorted(missing_checks))}")


def assert_cascade_delete(engine: Engine) -> None:
    with engine.begin() as connection:
        plant_id = connection.execute(
            text("INSERT INTO plants (nickname) VALUES ('Migration test') RETURNING id")
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
        connection.execute(text("DELETE FROM plants WHERE id = :id"), {"id": plant_id})

        for table in ("observations", "photos", "care_events", "assessments"):
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
