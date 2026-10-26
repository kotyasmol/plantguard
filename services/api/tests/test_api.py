from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from plantguard_api.config import Settings, get_settings
from plantguard_api.dependencies import get_photo_link_signer, get_photo_storage
from plantguard_api.main import app
from plantguard_api.photo_links import PhotoLinkSigner
from plantguard_api.photo_storage import LocalPhotoStorage


def image_bytes(image_format: str = "JPEG", size: tuple[int, int] = (4, 4)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=(42, 125, 76)).save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.fixture
def client(tmp_path: Path):
    configuration = Settings(
        _env_file=None,
        max_image_bytes=2048,
        max_image_pixels=100,
        photo_storage_path=tmp_path,
        photo_signing_key="test-photo-signing-key-with-32-characters",
    )
    storage = LocalPhotoStorage(tmp_path)
    signer = PhotoLinkSigner(configuration.photo_signing_key)
    app.dependency_overrides[get_settings] = lambda: configuration
    app.dependency_overrides[get_photo_storage] = lambda: storage
    app.dependency_overrides[get_photo_link_signer] = lambda: signer
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_endpoint(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "plantguard-api"}


def test_observation_validation_accepts_supported_image_without_claiming_persistence(
    client: TestClient,
):
    response = client.post(
        "/api/v1/observations/validate",
        files={"photo": ("leaf.jpg", image_bytes(), "image/jpeg")},
        data={"description": "Желтеют нижние листья", "humidity_pct": "74"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "validated"
    assert response.json()["persisted"] is False
    assert response.json()["analysis_started"] is False


def test_observation_rejects_non_image(client: TestClient):
    response = client.post(
        "/api/v1/observations/validate",
        files={"photo": ("notes.txt", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 415


def test_observation_rejects_invalid_humidity(client: TestClient):
    response = client.post(
        "/api/v1/observations/validate",
        files={"photo": ("leaf.png", image_bytes("PNG"), "image/png")},
        data={"humidity_pct": "120"},
    )

    assert response.status_code == 422


def test_observation_rejects_spoofed_image_media_type(client: TestClient):
    response = client.post(
        "/api/v1/observations/validate",
        files={"photo": ("leaf.jpg", b"plain-text", "image/jpeg")},
    )

    assert response.status_code == 422


def test_photo_upload_download_and_delete(client: TestClient, tmp_path: Path):
    content = image_bytes("PNG")

    upload = client.post(
        "/api/v1/photos",
        files={"photo": ("leaf.png", content, "image/png")},
    )

    assert upload.status_code == 201
    result = upload.json()
    assert result["media_type"] == "image/png"
    assert result["size_bytes"] == len(content)
    assert result["checksum_sha256"] == sha256(content).hexdigest()
    assert result["width"] == 4
    assert result["height"] == 4
    assert len(list(tmp_path.rglob("*.png"))) == 1

    download = client.get(result["read_url"])
    assert download.status_code == 200
    assert download.content == content
    assert download.headers["x-content-type-options"] == "nosniff"

    deletion = client.delete(result["delete_url"])
    assert deletion.status_code == 204
    assert not list(tmp_path.rglob("*.png"))
    assert client.get(result["read_url"]).status_code == 404


def test_photo_upload_rejects_corrupted_image(client: TestClient):
    response = client.post(
        "/api/v1/photos",
        files={"photo": ("leaf.jpg", b"\xff\xd8\xffcorrupted", "image/jpeg")},
    )

    assert response.status_code == 422
    assert "повреждён" in response.json()["detail"]


def test_photo_upload_rejects_mismatched_media_type(client: TestClient):
    response = client.post(
        "/api/v1/photos",
        files={"photo": ("leaf.jpg", image_bytes("PNG"), "image/jpeg")},
    )

    assert response.status_code == 422
    assert "не соответствует" in response.json()["detail"]


def test_photo_upload_rejects_file_over_size_limit(client: TestClient):
    response = client.post(
        "/api/v1/photos",
        files={"photo": ("large.png", b"x" * 2049, "image/png")},
    )

    assert response.status_code == 413


def test_photo_upload_rejects_excessive_pixel_count(client: TestClient):
    response = client.post(
        "/api/v1/photos",
        files={"photo": ("large.png", image_bytes("PNG", (11, 10)), "image/png")},
    )

    assert response.status_code == 413
    assert "Разрешение" in response.json()["detail"]


def test_read_link_cannot_be_used_to_delete_photo(client: TestClient):
    upload = client.post(
        "/api/v1/photos",
        files={"photo": ("leaf.webp", image_bytes("WEBP"), "image/webp")},
    )
    result = upload.json()

    read_query = result["read_url"].split("?", maxsplit=1)[1]
    delete_path = result["delete_url"].split("?", maxsplit=1)[0]
    response = client.delete(f"{delete_path}?{read_query}")

    assert response.status_code == 403
    assert client.get(result["read_url"]).status_code == 200
