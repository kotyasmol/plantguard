from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from plantguard_api.config import Settings, get_settings
from plantguard_api.database import Base, get_session
from plantguard_api.dependencies import get_photo_link_signer, get_photo_storage
from plantguard_api.main import app
from plantguard_api.photo_links import PhotoLinkSigner
from plantguard_api.photo_storage import LocalPhotoStorage
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (4, 4), color=(42, 125, 76)).save(buffer, format="JPEG")
    return buffer.getvalue()


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
    yield
    app.dependency_overrides.clear()
    engine.dispose()


def test_plant_history_survives_api_restart(history_client):
    with TestClient(app) as client:
        plant = client.post(
            "/api/v1/plants",
            json={"nickname": "Моя монстера", "species_status": "unconfirmed"},
        )
        assert plant.status_code == 201
        plant_id = plant.json()["id"]

        first = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("first.jpg", image_bytes(), "image/jpeg")},
            data={"description": "Появилось жёлтое пятно", "humidity_pct": "78"},
        )
        second = client.post(
            f"/api/v1/plants/{plant_id}/observations",
            files={"photo": ("repeat.jpg", image_bytes(), "image/jpeg")},
            data={"description": "Повторный снимок", "temperature_c": "23.5"},
        )
        care = client.post(
            f"/api/v1/plants/{plant_id}/care-events",
            json={"action_type": "watered", "notes": "Полив 250 мл"},
        )
        assert first.status_code == second.status_code == care.status_code == 201

    with TestClient(app) as restarted_client:
        history = restarted_client.get(f"/api/v1/plants/{plant_id}/history")

    assert history.status_code == 200
    payload = history.json()
    assert payload["plant"]["nickname"] == "Моя монстера"
    assert len(payload["observations"]) == 2
    assert {item["photos"][0]["original_filename"] for item in payload["observations"]} == {
        "first.jpg",
        "repeat.jpg",
    }
    assert payload["care_events"][0]["action_type"] == "watered"


def test_history_returns_not_found_for_unknown_plant(history_client):
    with TestClient(app) as client:
        response = client.get("/api/v1/plants/00000000-0000-0000-0000-000000000000/history")

    assert response.status_code == 404
