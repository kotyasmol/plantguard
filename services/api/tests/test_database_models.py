from plantguard_api.database import Base
from sqlalchemy.orm import configure_mappers


def test_domain_model_contains_expected_tables():
    configure_mappers()

    assert set(Base.metadata.tables) == {
        "plants",
        "observations",
        "photos",
        "care_events",
        "assessments",
    }


def test_dependent_records_are_deleted_with_their_parent():
    foreign_keys = {
        (table.name, foreign_key.parent.name): foreign_key.ondelete
        for table in Base.metadata.tables.values()
        for foreign_key in table.foreign_keys
    }

    assert foreign_keys[("observations", "plant_id")] == "CASCADE"
    assert foreign_keys[("photos", "observation_id")] == "CASCADE"
    assert foreign_keys[("care_events", "plant_id")] == "CASCADE"
    assert foreign_keys[("assessments", "observation_id")] == "CASCADE"
    assert foreign_keys[("assessments", "previous_assessment_id")] == "SET NULL"
