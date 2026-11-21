import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from plantguard_api.events import EVENT_MODELS

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts" / "events"
FIXTURES = ROOT / "tests" / "fixtures" / "events"


def test_every_event_contract_has_a_valid_example():
    schema_paths = sorted(SCHEMAS.glob("*.schema.json"))

    assert schema_paths, "No event contracts found"
    for schema_path in schema_paths:
        fixture_path = FIXTURES / schema_path.name.replace(".schema", "")
        assert fixture_path.exists(), f"Missing fixture for {schema_path.name}"

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(fixture)


def test_typed_consumers_and_producers_follow_the_json_contracts():
    schema_paths = sorted(SCHEMAS.glob("*.schema.json"))

    assert set(EVENT_MODELS) == {path.name for path in schema_paths}
    for schema_path in schema_paths:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        fixture_path = FIXTURES / schema_path.name.replace(".schema", "")
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        consumed = EVENT_MODELS[schema_path.name].model_validate(fixture)
        produced = consumed.model_dump(mode="json", exclude_none=True)

        Draft202012Validator(schema, format_checker=FormatChecker()).validate(produced)
        assert produced["plant_id"] == fixture["plant_id"]


def test_every_contract_declares_topic_key_version_and_timestamp():
    for schema_path in SCHEMAS.glob("*.schema.json"):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        assert schema["x-kafka-topic"].startswith("plant.")
        assert schema["x-kafka-key"] == "plant_id"
        assert {
            "event_id",
            "event_type",
            "schema_version",
            "occurred_at",
            "plant_id",
        } <= set(schema["required"])
        assert schema["properties"]["schema_version"]["const"] == 1
        assert schema["properties"]["occurred_at"]["type"] == "integer"


def test_unknown_event_fields_are_rejected():
    schema = json.loads(
        (SCHEMAS / "plant-observation.v1.schema.json").read_text(encoding="utf-8")
    )
    fixture = json.loads(
        (FIXTURES / "plant-observation.v1.json").read_text(encoding="utf-8")
    )
    fixture["unexpected"] = True

    errors = list(Draft202012Validator(schema).iter_errors(fixture))

    assert errors
