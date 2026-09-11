import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

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
