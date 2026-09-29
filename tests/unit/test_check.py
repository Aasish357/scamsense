import pytest
from uuid import uuid4

from apps.web.src.app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def auth_headers():
    """Register + log in a fresh user and return the bearer header."""
    username = "check-{}".format(uuid4().hex[:8])
    client.post(
        "/register",
        json={"username": username, "email": username + "@example.com", "password": "secret"},
    )
    login = client.post("/login", json={"username": username, "password": "secret"})
    return {"Authorization": "Bearer " + login.json()["token"]}


@pytest.mark.parametrize(
    "content, expected_score, expected_evidence, expected_level",
    [
        # Scoring is detector-driven: naming a brand we trust is informational
        # (0), and a plain-http link on a real domain is a weak signal (the
        # evaluation harness replaced the old "any URL = 70" placeholder).
        ("This is a message about ExampleBrand.", 0, "Trusted brand detected.", "low"),
        ("This is a message about TestBrand.", 50, "Untrusted brand detected.", "suspicious"),
        ("No brand mentioned here.", 0, "No notable risk signals detected.", "low"),
        ("Please open https://www.example.com now.", 0, "Link structure looks ordinary", "low"),
        ("Please open http://example.com now.", 45, "non-HTTPS link", "caution"),
    ],
)
def test_analyze_content(content, expected_score, expected_evidence, expected_level):
    headers = auth_headers()
    response = client.post("/check", json={"content": content}, headers=headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["analysis_id"]
    assert payload["created_at"]
    assert payload["risk_score"] == expected_score
    assert expected_evidence in payload["evidence"]
    assert payload["risk_level"] == expected_level

    stored = client.get("/analyses/{}".format(payload["analysis_id"]), headers=headers)
    assert stored.status_code == 200
    assert stored.json()["analysis_id"] == payload["analysis_id"]
    assert stored.json()["risk_score"] == expected_score

    history = client.get("/api/v1/me/analyses", headers=headers)
    assert history.status_code == 200
    assert any(item["analysis_id"] == payload["analysis_id"] for item in history.json())


def test_history_requires_authentication():
    assert client.get("/api/v1/me/analyses").status_code == 401


def test_guest_analysis_is_readable_but_never_in_user_history():
    guest = client.post("/check", json={"content": "No brand mentioned here."})
    assert guest.status_code == 200
    guest_id = guest.json()["analysis_id"]

    # Guest records stay readable by anyone holding the id...
    assert client.get("/analyses/{}".format(guest_id)).status_code == 200

    # ...but they are never exposed through an authenticated user's history,
    # and they cannot be deleted without ownership.
    headers = auth_headers()
    history = client.get("/api/v1/me/analyses", headers=headers)
    assert all(item["analysis_id"] != guest_id for item in history.json())
    assert client.delete("/analyses/{}".format(guest_id), headers=headers).status_code == 404