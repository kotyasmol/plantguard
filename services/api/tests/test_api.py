from fastapi.testclient import TestClient
from plantguard_api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "plantguard-api"}


def test_observation_accepts_supported_image():
    response = client.post(
        "/api/v1/observations",
        files={"photo": ("leaf.jpg", b"\xff\xd8\xffexample-image-bytes", "image/jpeg")},
        data={"description": "Желтеют нижние листья", "humidity_pct": "74"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"


def test_observation_rejects_non_image():
    response = client.post(
        "/api/v1/observations",
        files={"photo": ("notes.txt", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 415


def test_observation_rejects_invalid_humidity():
    response = client.post(
        "/api/v1/observations",
        files={"photo": ("leaf.png", b"\x89PNG\r\n\x1a\nexample-image-bytes", "image/png")},
        data={"humidity_pct": "120"},
    )

    assert response.status_code == 422


def test_observation_rejects_spoofed_image_media_type():
    response = client.post(
        "/api/v1/observations",
        files={"photo": ("leaf.jpg", b"plain-text", "image/jpeg")},
    )

    assert response.status_code == 422
