from fastapi.testclient import TestClient

from apps.web.src.app.main import app

client = TestClient(app)

_ADMIN_KEY = "secret-admin-key"


def test_reports_accept_guest_and_authenticated_submissions():
    guest = client.post(
        "/reports",
        json={"analysis_id": "abc", "reason": "phishing", "message": "looks fake"},
    )
    assert guest.status_code == 200
    assert guest.json()["msg"] == "Report submitted successfully!"


def test_admin_api_disabled_without_configured_key(monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    assert client.get("/admin/overview").status_code == 503


def test_admin_api_rejects_missing_or_wrong_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", _ADMIN_KEY)
    assert client.get("/admin/overview").status_code == 401
    assert client.get("/admin/overview", headers={"x-admin-key": "nope"}).status_code == 401


def test_admin_overview_lists_reports_and_stats(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", _ADMIN_KEY)
    client.post("/reports", json={"analysis_id": "xyz", "reason": "scam", "message": "urgent"})
    client.post(
        "/feedback", json={"username": "tester", "message": "feedback from admin test"}
    )

    response = client.get("/admin/overview", headers={"x-admin-key": _ADMIN_KEY})
    assert response.status_code == 200

    payload = response.json()
    assert payload["stats"]["reports"] >= 1
    assert payload["stats"]["analyses"] >= 0
    assert "average_risk_score" in payload["stats"]
    assert any(item.get("analysis_id") == "xyz" for item in payload["reports"])
    assert isinstance(payload["recent_analyses"], list)