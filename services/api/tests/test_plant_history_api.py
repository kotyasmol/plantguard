from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from plantguard_api.config import Settings, get_settings
from plantguard_api.database import Assessment, Base, OutboxEvent, get_session
from plantguard_api.database.models import EnvironmentReading, Plant, PlantAlert
from plantguard_api.dependencies import (
    get_photo_comparator,
    get_photo_link_signer,
    get_photo_storage,
    get_plant_identifier,
    get_symptom_extractor,
    get_visual_condition_analyzer,
)
from plantguard_api.main import app
from plantguard_api.photo_links import PhotoLinkSigner
from plantguard_api.photo_storage import LocalPhotoStorage
from plantguard_api.security import DUMMY_PASSWORD_HASH
from plantguard_mining import (
    Evidence,
    IdentificationCandidate,
    IdentificationOutcome,
    PhotoComparisonOutcome,
    TextAnalysisOutcome,
    VisualAnalysisOutcome,
)
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker


def image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (4, 4), color=(42, 125, 76)).save(buffer, format="JPEG")
    return buffer.getvalue()


def register(client: TestClient, email: str = "owner@example.com") -> dict[str, str]:
    response = client.post(
        "/api/v1/users",
        json={"email": email, "display_name": "Владелец", "password": "safe-test-password"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_registered_user_can_sign_in_again(history_client):
    with TestClient(app) as client:
        first_headers = register(client, "returning@example.com")
        login = client.post(
            "/api/v1/sessions",
            json={"email": "RETURNING@example.com", "password": "safe-test-password"},
        )

        assert login.status_code == 200
        second_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/api/v1/users/me", headers=second_headers).status_code == 200
        assert client.get("/api/v1/users/me", headers=first_headers).status_code == 401


def test_sign_in_does_not_reveal_which_credential_is_wrong(history_client):
    with TestClient(app) as client:
        register(client, "auth-errors@example.com")
        wrong_password = client.post(
            "/api/v1/sessions",
            json={"email": "auth-errors@example.com", "password": "wrong-password"},
        )
        unknown_email = client.post(
            "/api/v1/sessions",
            json={"email": "unknown@example.com", "password": "wrong-password"},
        )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_unknown_email_still_runs_password_verification(history_client):
    with patch("plantguard_api.users.verify_password", return_value=False) as verifier:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/sessions",
                json={"email": "unknown@example.com", "password": "wrong-password"},
            )

    assert response.status_code == 401
    verifier.assert_called_once_with("wrong-password", DUMMY_PASSWORD_HASH)


@pytest.fixture
def history_client(tmp_path: Path):
    database_path = tmp_path / "history.sqlite3"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False, class_=Session)
    configuration = Settings(
        _env_file=None,
        database_url=f"sqlite+pysqlite:///{database_path}",
        photo_storage_path=tmp_path / "photos",
        photo_signing_key="test-photo-signing-key-with-32-characters",
    )
    storage = LocalPhotoStorage(configuration.photo_storage_path)
    signer = PhotoLinkSigner(configuration.photo_signing_key)

    def session_override():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: configuration
    app.dependency_overrides[get_photo_storage] = lambda: storage
    app.dependency_overrides[get_photo_link_signer] = lambda: signer
    yield session_factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def reading_endpoint(history_client):
    with TestClient(app) as client:
        headers = register(client)
        plant = client.post("/api/v1/plants", headers=headers, json={"nickname": "Aloe"})
        assert plant.status_code == 201
        yield client, headers, f"/api/v1/plants/{plant.json()['id']}/environment-readings"


@pytest.mark.parametrize("values", [
    {"humidity_pct": 0}, {"temperature_c": -50}, {"temperature_c": 70, "humidity_pct": 100},
])
def test_manual_reading_persists_and_queues_event(history_client, reading_endpoint, values):
    client, headers, url = reading_endpoint
    response = client.post(url, headers=headers, json=values)
    assert response.status_code == 201
    result = response.json()
    with history_client() as session:
        reading = session.scalars(select(EnvironmentReading)).one()
        queued = session.scalars(select(OutboxEvent)).one()
        assert str(reading.id) == result["id"] == queued.payload["event_id"]
        assert str(reading.plant_id) == result["plant_id"] == queued.message_key
        assert queued.topic == "plant.environment-readings.v1"
        assert queued.payload["source"] == "manual"
        for key in ("humidity_pct", "temperature_c"):
            assert getattr(reading, key) == result[key] == values.get(key)
            assert (key in queued.payload) == (key in values)
            assert queued.payload.get(key) == values.get(key)


def test_manual_reading_rejects_invalid_values_and_other_owners(history_client, reading_endpoint):
    client, headers, url = reading_endpoint
    for values in ({}, {"humidity_pct": None}, {"humidity_pct": 101}, {"temperature_c": -51}):
        assert client.post(url, headers=headers, json=values).status_code == 422
    values = {"temperature_c": 18.75}
    assert client.post(url, json=values).status_code == 401
    other = register(client, "other@example.com")
    assert client.post(url, headers=other, json=values).status_code == 404
    with history_client() as session:
        assert session.scalar(select(EnvironmentReading)) is None
        assert session.scalar(select(OutboxEvent)) is None


def test_reading_history_filters_by_plant_and_limits_newest_first(reading_endpoint):
    client, headers, url = reading_endpoint
    assert client.get(url, headers=headers).json() == []
    other_plant = client.post("/api/v1/plants", headers=headers, json={"nickname": "Mint"})
    other_url = f"/api/v1/plants/{other_plant.json()['id']}/environment-readings"
    assert client.post(other_url, headers=headers, json={"humidity_pct": 99}).status_code == 201
    ids = []
    for humidity in (42, 55, 68):
        response = client.post(url, headers=headers, json={"humidity_pct": humidity})
        assert response.status_code == 201
        ids.append(response.json()["id"])

    history = client.get(url, headers=headers)
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == ids[::-1]
    recent = client.get(url, headers=headers, params={"limit": 2})
    assert recent.json() == history.json()[:2]
    assert [item["humidity_pct"] for item in recent.json()] == [68, 55]


def test_reading_history_requires_owner_and_valid_limit(reading_endpoint):
    client, headers, url = reading_endpoint
    assert client.get(url).status_code == 401
    other = register(client, "another@example.com")
    assert client.get(url, headers=other).status_code == 404
    for limit in (0, 101):
        assert client.get(url, headers=headers, params={"limit": limit}).status_code == 422


def test_manual_reading_rolls_back_when_enqueue_fails(history_client, reading_endpoint):
    client, headers, url = reading_endpoint
    with patch("plantguard_api.plant_history.enqueue_event", side_effect=RuntimeError("outbox")):
        with pytest.raises(RuntimeError, match="outbox"):
            client.post(url, headers=headers, json={"humidity_pct": 64.5})
    with history_client() as session:
        assert session.scalar(select(EnvironmentReading)) is None
        assert session.scalar(select(OutboxEvent)) is None


@pytest.fixture
def alerts_for_two_owners(history_client):
    with TestClient(app) as client:
        owner = register(client)
        other = register(client, "second@example.com")
        alerts = []
        for day, headers in enumerate([owner, owner, other], start=1):
            plant = client.post("/api/v1/plants", headers=headers, json={"nickname": "Fern"})
            with history_client() as session:
                alert = PlantAlert(
                    plant_id=UUID(plant.json()["id"]), event_id=str(uuid4()),
                    occurred_at=datetime(2026, 1, day, tzinfo=timezone.utc),
                    severity="warning", alert_code="humidity_too_low",
                )
                session.add(alert)
                session.commit()
                alerts.append(alert.id)
        yield client, owner, other, alerts


def test_alert_list_is_scoped_to_owner_and_ordered(alerts_for_two_owners):
    client, owner, other, (older, newer, foreign) = alerts_for_two_owners
    url = "/api/v1/alerts"
    assert client.get(url).status_code == 401
    result = client.get(url, headers=owner)
    assert result.status_code == 200
    assert [item["id"] for item in result.json()] == [str(newer), str(older)]
    assert [item["id"] for item in client.get(url, headers=other).json()] == [str(foreign)]


def test_acknowledgement_preserves_first_timestamp_and_filters_unread(alerts_for_two_owners):
    client, owner, other, (older, newer, _) = alerts_for_two_owners
    url = f"/api/v1/alerts/{newer}/acknowledge"
    assert client.post(url).status_code == 401
    assert client.post(url, headers=other).status_code == 404
    assert client.post(f"/api/v1/alerts/{uuid4()}/acknowledge", headers=owner).status_code == 404
    first = client.post(url, headers=owner)
    assert first.status_code == 200
    assert first.json()["acknowledged_at"]
    assert client.post(url, headers=owner).json() == first.json()
    unread = client.get("/api/v1/alerts?unread=true", headers=owner).json()
    assert [item["id"] for item in unread] == [str(older)]
    assert unread[0]["acknowledged_at"] is None
    assert client.get("/api/v1/alerts", headers=owner).json()[0] == first.json()


def test_alerts_deleted_with_plant_and_profile(alerts_for_two_owners, history_client):
    client, owner, other, (older, newer, foreign) = alerts_for_two_owners
    with history_client() as session:
        alert = session.get(PlantAlert, older)
        session.delete(session.get(Plant, alert.plant_id))
        session.commit()
    assert [item["id"] for item in client.get("/api/v1/alerts", headers=owner).json()] == [
        str(newer)
    ]
    assert client.delete("/api/v1/users/me", headers=owner).status_code == 204
    with history_client() as session:
        assert session.scalars(select(PlantAlert.id)).all() == [foreign]
    assert client.get("/api/v1/alerts", headers=other).json()[0]["id"] == str(foreign)


def test_care_schedule_follows_latest_action_and_can_be_disabled(reading_endpoint):
    client, headers, reading_url = reading_endpoint
    plant_url = reading_url.rsplit("/", 1)[0]
    url = f"{plant_url}/care-schedule"
    initial = client.get(url, headers=headers).json()
    assert initial == dict.fromkeys(("watering_days", "feeding_days", "watering_due_at",
                                     "feeding_due_at"))
    intervals = {"watering_days": 7, "feeding_days": 30}
    result = client.put(url, headers=headers, json=intervals)
    assert result.status_code == 200
    assert result.json()["watering_due_at"] is None
    for action, day in [("watered", 15), ("watered", 3), ("fertilized", 1), ("moved", 20)]:
        event = {"action_type": action, "performed_at": f"2026-11-{day:02d}T12:00:00Z"}
        saved = client.post(f"{plant_url}/care-events", headers=headers, json=event)
        assert saved.status_code == 201
    schedule = client.get(url, headers=headers).json()
    assert schedule == {
        **intervals, "watering_due_at": "2026-11-22T12:00:00Z",
        "feeding_due_at": "2026-12-01T12:00:00Z",
    }
    intervals["watering_days"] = None
    changed = client.put(url, headers=headers, json=intervals).json()
    assert changed["watering_due_at"] is None
    assert changed["feeding_due_at"] == schedule["feeding_due_at"]


def test_care_schedule_enforces_owner_and_intervals(reading_endpoint):
    client, headers, reading_url = reading_endpoint
    url = reading_url.rsplit("/", 1)[0] + "/care-schedule"
    other = register(client, "other-schedule@example.com")
    assert client.get(url).status_code == 401
    assert client.get(url, headers=other).status_code == 404
    values = {"watering_days": 7, "feeding_days": 365}
    assert client.put(url, headers=other, json=values).status_code == 404
    for invalid in (0, 366, 1.5, True):
        response = client.put(url, headers=headers, json={**values, "watering_days": invalid})
        assert response.status_code == 422
    assert client.get(url, headers=headers).json()["watering_days"] is None


def test_plant_history_survives_api_restart(history_client):
    with TestClient(app) as client:
        headers = register(client)
        plant = client.post(
            "/api/v1/plants",
            json={"nickname": "Моя монстера", "species_status": "unconfirmed"},
            headers=headers,
        )
        assert plant.status_code == 201
        plant_id = plant.json()["id"]

        first = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("first.jpg", image_bytes(), "image/jpeg")},
            data={"description": "Появилось жёлтое пятно", "humidity_pct": "78"},
            headers=headers,
        )
        second = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("repeat.jpg", image_bytes(), "image/jpeg")},
            data={"description": "Повторный снимок", "temperature_c": "23.5"},
            headers=headers,
        )
        care = client.post(
            f"/api/v1/plants/{plant_id}/care-events",
            json={"action_type": "watered", "notes": "Полив 250 мл"},
            headers=headers,
        )
        assert first.status_code == second.status_code == care.status_code == 201

    with TestClient(app) as restarted_client:
        history = restarted_client.get(
            f"/api/v1/plants/{plant_id}/history", headers=headers
        )

    assert history.status_code == 200
    payload = history.json()
    assert payload["plant"]["nickname"] == "Моя монстера"
    assert len(payload["observations"]) == 2
    assert {item["photos"][0]["original_filename"] for item in payload["observations"]} == {
        "first.jpg",
        "repeat.jpg",
    }
    assert payload["care_events"][0]["action_type"] == "watered"
    assert payload["assessments"] == []
    with history_client() as session:
        queued = session.scalars(select(OutboxEvent).order_by(OutboxEvent.created_at)).all()
    assert [event.topic for event in queued] == [
        "plant.observations.v1",
        "plant.observations.v1",
        "plant.care-events.v1",
    ]
    assert {event.message_key for event in queued} == {plant_id}


def test_history_returns_not_found_for_unknown_plant(history_client):
    with TestClient(app) as client:
        headers = register(client)
        response = client.get(
            "/api/v1/plants/00000000-0000-0000-0000-000000000000/history",
            headers=headers,
        )

    assert response.status_code == 404


def test_plant_list_only_contains_current_users_plants(history_client):
    with TestClient(app) as client:
        first_user = register(client, "list-first@example.com")
        second_user = register(client, "list-second@example.com")
        client.post(
            "/api/v1/plants", json={"nickname": "Монстера"}, headers=first_user
        )
        client.post(
            "/api/v1/plants", json={"nickname": "Фикус"}, headers=second_user
        )

        response = client.get("/api/v1/plants", headers=first_user)

    assert response.status_code == 200
    assert [plant["nickname"] for plant in response.json()] == ["Монстера"]


def test_users_cannot_access_or_modify_each_others_plants(history_client):
    with TestClient(app) as client:
        first_user = register(client, "first@example.com")
        second_user = register(client, "second@example.com")
        plant = client.post(
            "/api/v1/plants", json={"nickname": "Частный фикус"}, headers=first_user
        )
        plant_id = plant.json()["id"]

        assert client.get(f"/api/v1/plants/{plant_id}", headers=second_user).status_code == 404
        assert (
            client.post(
                f"/api/v1/plants/{plant_id}/care-events",
                json={"action_type": "watered"},
                headers=second_user,
            ).status_code
            == 404
        )
        assert client.get(f"/api/v1/plants/{plant_id}", headers=first_user).status_code == 200


def test_deleting_profile_removes_owned_data_and_photos(history_client):
    with TestClient(app) as client:
        headers = register(client, "delete@example.com")
        plant_id = client.post(
            "/api/v1/plants", json={"nickname": "Удаляемое растение"}, headers=headers
        ).json()["id"]
        observation = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("private.jpg", image_bytes(), "image/jpeg")},
            headers=headers,
        ).json()
        read_url = observation["photos"][0]["read_url"]

        assert client.delete("/api/v1/users/me", headers=headers).status_code == 204
        assert client.get(read_url).status_code == 404
        assert client.get(f"/api/v1/plants/{plant_id}", headers=headers).status_code == 401


def test_identification_suggests_species_and_manual_correction_confirms_it(history_client):
    class FakeIdentifier:
        def identify(self, _image):
            return IdentificationOutcome(
                candidates=(
                    IdentificationCandidate(
                        "monstera_deliciosa", "Монстера деликатесная", 0.91
                    ),
                    IdentificationCandidate(
                        "epipremnum_aureum", "Эпипремнум золотистый", 0.06
                    ),
                    IdentificationCandidate(
                        "ficus_elastica", "Фикус каучуконосный", 0.03
                    ),
                    IdentificationCandidate(
                        "crassula_ovata", "Толстянка яйцевидная", 0.0
                    ),
                    IdentificationCandidate(
                        "dracaena_fragrans", "Драцена душистая", 0.0
                    ),
                ),
                recognized=True,
                model_version="fake-species-model",
            )

    app.dependency_overrides[get_plant_identifier] = lambda: FakeIdentifier()
    with TestClient(app) as client:
        headers = register(client, "identify@example.com")
        plant_id = client.post(
            "/api/v1/plants", json={"nickname": "Неизвестное растение"}, headers=headers
        ).json()["id"]
        observation = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("plant.jpg", image_bytes(), "image/jpeg")},
            headers=headers,
        ).json()

        identification = client.post(
            f"/api/v1/plants/{plant_id}/observations/{observation['id']}/identify",
            headers=headers,
        )
        suggested = client.get(f"/api/v1/plants/{plant_id}", headers=headers)
        corrected = client.patch(
            f"/api/v1/plants/{plant_id}/species",
            json={
                "scientific_name": "Epipremnum aureum",
                "common_name": "Эпипремнум золотистый",
            },
            headers=headers,
        )

    assert identification.status_code == 200
    assert identification.json()["recognized"] is True
    assert len(identification.json()["candidates"]) == 5
    assert suggested.json()["species_status"] == "suggested"
    assert suggested.json()["species_scientific_name"] == "Monstera deliciosa"
    assert corrected.json()["species_status"] == "confirmed"
    assert corrected.json()["species_scientific_name"] == "Epipremnum aureum"
    with history_client() as session:
        identification_events = session.scalars(
            select(OutboxEvent).where(
                OutboxEvent.topic == "plant.identification-results.v1"
            )
        ).all()
    assert len(identification_events) == 1
    assert len(identification_events[0].payload["candidates"]) == 3


def test_identification_accepts_species_outside_local_catalog(history_client):
    class BroadIdentifier:
        def identify(self, _image):
            return IdentificationOutcome(
                candidates=(
                    IdentificationCandidate(
                        "crassula_ovata",
                        "Толстянка яйцевидная",
                        0.94,
                        scientific_name="Crassula ovata",
                        common_name="Толстянка яйцевидная",
                    ),
                ),
                recognized=True,
                model_version="broad-catalog-test",
            )

    app.dependency_overrides[get_plant_identifier] = lambda: BroadIdentifier()
    with TestClient(app) as client:
        headers = register(client, "broad-catalog@example.com")
        plant_id = client.post(
            "/api/v1/plants", json={"nickname": "Толстянка"}, headers=headers
        ).json()["id"]
        observation = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("plant.jpg", image_bytes(), "image/jpeg")},
            headers=headers,
        ).json()

        response = client.post(
            f"/api/v1/plants/{plant_id}/observations/{observation['id']}/identify",
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json()["candidates"][0] == {
        "species_code": "crassula_ovata",
        "scientific_name": "Crassula ovata",
        "common_name": "Толстянка яйцевидная",
        "confidence": 0.94,
    }


def test_visual_analysis_returns_structured_findings(history_client):
    class FakeAnalyzer:
        def analyze(self, _image):
            return VisualAnalysisOutcome(
                findings=(Evidence("leaf-yellowing", 0.82, "image:test"),),
                analyzable=True,
                model_version="fake-visual-model",
            )

    app.dependency_overrides[get_visual_condition_analyzer] = lambda: FakeAnalyzer()
    with TestClient(app) as client:
        headers = register(client, "visual@example.com")
        plant_id = client.post(
            "/api/v1/plants", json={"nickname": "Лист"}, headers=headers
        ).json()["id"]
        observation_id = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("leaf.jpg", image_bytes(), "image/jpeg")},
            headers=headers,
        ).json()["id"]

        response = client.post(
            f"/api/v1/plants/{plant_id}/observations/{observation_id}/analyze-visual",
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json() == {
        "observation_id": observation_id,
        "analyzable": True,
        "findings": [{"code": "leaf-yellowing", "confidence": 0.82}],
        "model_version": "fake-visual-model",
    }


def test_text_analysis_uses_stored_description(history_client):
    class FakeExtractor:
        def extract(self, description):
            assert description == "Лист начал желтеть"
            return TextAnalysisOutcome(
                findings=(Evidence("leaf-yellowing", 0.92, "text:test"),),
                analyzable=True,
                model_version="fake-text-model",
            )

    app.dependency_overrides[get_symptom_extractor] = lambda: FakeExtractor()
    with TestClient(app) as client:
        headers = register(client, "text@example.com")
        plant_id = client.post(
            "/api/v1/plants", json={"nickname": "Описание"}, headers=headers
        ).json()["id"]
        observation_id = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("leaf.jpg", image_bytes(), "image/jpeg")},
            data={"description": "Лист начал желтеть"},
            headers=headers,
        ).json()["id"]

        response = client.post(
            f"/api/v1/plants/{plant_id}/observations/{observation_id}/analyze-text",
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json()["findings"] == [
        {"code": "leaf-yellowing", "confidence": 0.92}
    ]


def test_photo_comparison_rejects_incompatible_pair(history_client):
    class FakeComparator:
        def compare(self, _first, _second):
            return PhotoComparisonOutcome(
                comparable=False,
                reasons=("framing_mismatch",),
                metrics={"structure_similarity": 0.31},
                model_version="fake-comparator",
            )

    app.dependency_overrides[get_photo_comparator] = lambda: FakeComparator()
    with TestClient(app) as client:
        headers = register(client, "compare@example.com")
        plant_id = client.post(
            "/api/v1/plants", json={"nickname": "Сравнение"}, headers=headers
        ).json()["id"]
        observation_ids = [
            client.post(
                f"/api/v1/plants/{plant_id}/observations",
                files={"photo": (f"leaf-{index}.jpg", image_bytes(), "image/jpeg")},
                headers=headers,
            ).json()["id"]
            for index in range(2)
        ]

        response = client.post(
            f"/api/v1/plants/{plant_id}/observations/{observation_ids[1]}"
            f"/compare/{observation_ids[0]}",
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json()["comparable"] is False
    assert response.json()["reasons"] == ["framing_mismatch"]


def test_dynamics_returns_changes_and_intervening_care_events(history_client):
    class ComparablePhotos:
        def compare(self, _first, _second):
            return PhotoComparisonOutcome(
                comparable=True,
                reasons=(),
                metrics={"structure_similarity": 0.91},
            )

    class SequentialAnalyzer:
        def __init__(self):
            self.calls = 0

        def analyze(self, _image):
            self.calls += 1
            findings = (
                (Evidence("leaf-yellowing", 0.88, "image:test"),)
                if self.calls == 1
                else (Evidence("leaf-yellowing", 0.54, "image:test"),)
            )
            return VisualAnalysisOutcome(findings=findings, analyzable=True)

    app.dependency_overrides[get_photo_comparator] = lambda: ComparablePhotos()
    app.dependency_overrides[get_visual_condition_analyzer] = lambda: SequentialAnalyzer()
    with TestClient(app) as client:
        headers = register(client, "dynamics@example.com")
        plant_id = client.post(
            "/api/v1/plants", json={"nickname": "Динамика"}, headers=headers
        ).json()["id"]
        previous_id = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("before.jpg", image_bytes(), "image/jpeg")},
            data={"observed_at": "2026-11-20T10:00:00+05:00"},
            headers=headers,
        ).json()["id"]
        client.post(
            f"/api/v1/plants/{plant_id}/care-events",
            json={
                "action_type": "moved",
                "notes": "Переставлено ближе к окну",
                "performed_at": "2026-11-21T10:00:00+05:00",
            },
            headers=headers,
        )
        current_id = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("after.jpg", image_bytes(), "image/jpeg")},
            data={"observed_at": "2026-11-22T10:00:00+05:00"},
            headers=headers,
        ).json()["id"]

        response = client.post(
            f"/api/v1/plants/{plant_id}/observations/{current_id}"
            f"/dynamics/{previous_id}",
            headers=headers,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["comparable"] is True
    assert payload["trend"] == "improving"
    assert payload["changes"] == [
        {
            "code": "leaf-yellowing",
            "previous_confidence": 0.88,
            "current_confidence": 0.54,
            "direction": "resolved",
        }
    ]
    assert [event["action_type"] for event in payload["care_events"]] == ["moved"]


def test_decision_support_combines_signals_and_persists_assessment(history_client):
    class DecisionIdentifier:
        def identify(self, _image):
            return IdentificationOutcome(
                candidates=(
                    IdentificationCandidate(
                        "monstera_deliciosa", "Монстера деликатесная", 0.91
                    ),
                    IdentificationCandidate(
                        "epipremnum_aureum", "Эпипремнум золотистый", 0.06
                    ),
                    IdentificationCandidate(
                        "ficus_elastica", "Фикус каучуконосный", 0.03
                    ),
                ),
                recognized=True,
                model_version="decision-id-test",
            )

    class DecisionVisualAnalyzer:
        def analyze(self, _image):
            return VisualAnalysisOutcome(
                findings=(Evidence("leaf-yellowing", 0.84, "image:test"),),
                analyzable=True,
                model_version="decision-visual-test",
            )

    class DecisionTextExtractor:
        def extract(self, _description):
            return TextAnalysisOutcome(
                findings=(Evidence("leaf-yellowing", 0.92, "text:test"),),
                analyzable=True,
                model_version="decision-text-test",
            )

    app.dependency_overrides[get_plant_identifier] = lambda: DecisionIdentifier()
    app.dependency_overrides[get_visual_condition_analyzer] = (
        lambda: DecisionVisualAnalyzer()
    )
    app.dependency_overrides[get_symptom_extractor] = lambda: DecisionTextExtractor()
    with TestClient(app) as client:
        headers = register(client, "decision@example.com")
        plant_id = client.post(
            "/api/v1/plants", json={"nickname": "СППР"}, headers=headers
        ).json()["id"]
        client.patch(
            f"/api/v1/plants/{plant_id}/species",
            json={
                "scientific_name": "Monstera deliciosa",
                "common_name": "Монстера деликатесная",
            },
            headers=headers,
        )
        observation_id = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("assessment.jpg", image_bytes(), "image/jpeg")},
            data={"description": "Лист начал желтеть", "humidity_pct": "55"},
            headers=headers,
        ).json()["id"]

        response = client.post(
            f"/api/v1/plants/{plant_id}/observations/{observation_id}/assess",
            headers=headers,
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["risk_level"] == "medium"
    assert payload["requires_more_data"] is False
    assert {item["source"] for item in payload["evidence"]} == {
        "image:test",
        "text:test",
    }
    assert "пожелтение" in payload["explanation"]
    assert payload["explanation_source"] == "deterministic"
    with history_client() as session:
        assessment = session.scalar(select(Assessment))
        events = session.scalars(
            select(OutboxEvent).where(
                OutboxEvent.topic == "plant.assessment-results.v1"
            )
        ).all()
    assert assessment is not None
    assert assessment.risk_level == "medium"
    assert "не диагноз" in assessment.explanation
    assert len(events) == 1
