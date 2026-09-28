from base64 import b64decode
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.web.src.app.main import app

client = TestClient(app)


def auth_headers():
    username = "api-{}".format(uuid4().hex[:8])
    client.post(
        "/register",
        json={"username": username, "email": username + "@example.com", "password": "secret"},
    )
    login = client.post("/login", json={"username": username, "password": "secret"})
    return {"Authorization": "Bearer " + login.json()["token"]}


def test_health_and_brand_endpoints():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    versioned_health = client.get("/api/v1/health")
    assert versioned_health.status_code == 200
    assert versioned_health.json() == {"status": "ok"}

    brand = client.get("/brand/ExampleBrand")
    assert brand.status_code == 200
    assert brand.json()["brand"] == "ExampleBrand"
    assert brand.json()["verified"] is True

    unknown_brand = client.get("/brand/UnknownBrand")
    assert unknown_brand.status_code == 404


def test_screenshot_analysis_uses_fallback_text_when_needed():
    sample_png = b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4//8/AwAI/AL+X4n3NwAAAABJRU5ErkJggg=="
    )
    response = client.post(
        "/screenshot",
        files={"file": ("sample.png", BytesIO(sample_png), "image/png")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["extracted_text"]
    assert payload["recommendations"] == "Analyze the content for suspicious patterns."


def test_delete_analysis_endpoint():
    headers = auth_headers()
    check_response = client.post("/check", json={"content": "Delete candidate"}, headers=headers)
    assert check_response.status_code == 200
    analysis_id = check_response.json()["analysis_id"]

    # Deleting without a token is refused outright.
    assert client.delete("/api/v1/analyses/{}".format(analysis_id)).status_code == 401

    # Delete existing
    del_response = client.delete("/api/v1/analyses/{}".format(analysis_id), headers=headers)
    assert del_response.status_code == 200
    assert del_response.json() == {"analysis_id": analysis_id, "deleted": True}

    # Delete non-existent
    del_404 = client.delete("/api/v1/analyses/{}".format(analysis_id), headers=headers)
    assert del_404.status_code == 404