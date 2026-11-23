from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from plantguard_api.config import Settings, get_settings
from plantguard_api.database import Assessment, Base, OutboxEvent, get_session
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
        "/api/v1/users", json={"email": email, "display_name": "Владелец"}
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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
    assert len(identification.json()["candidates"]) == 3
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
