import base64
import hashlib
import hmac
import json
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.web.src.app.api import auth as auth_module
from apps.web.src.app.main import app

client = TestClient(app)


def make_user(prefix):
    username = "{}-{}".format(prefix, uuid4().hex[:8])
    client.post(
        "/register",
        json={"username": username, "email": username + "@example.com", "password": "secret"},
    )
    login = client.post("/login", json={"username": username, "password": "secret"})
    token = login.json()["token"]
    return username, {"Authorization": "Bearer " + token}, token


def test_login_returns_a_signed_token():
    username, headers, token = make_user("tok")
    assert token.count(".") == 1
    assert auth_module.parse_token(token) == username


def test_tokens_reject_tampering_and_expiry():
    username, _, token = make_user("tamper")
    raw, signature = token.split(".", 1)
    assert auth_module.parse_token("{}.{}".format(raw, "0" * len(signature))) is None
    assert auth_module.parse_token("garbage") is None

    expired_payload = base64.urlsafe_b64encode(
        json.dumps({"sub": username, "exp": 1}).encode("utf-8")
    ).decode("ascii")
    expired_sig = hmac.new(
        auth_module._secret(), expired_payload.encode("ascii"), hashlib.sha256
    ).hexdigest()
    assert auth_module.parse_token("{}.{}".format(expired_payload, expired_sig)) is None


def test_history_is_scoped_to_the_logged_in_user():
    _, alex, _ = make_user("alex")
    _, blake, _ = make_user("blake")

    created = client.post("/check", json={"content": "No brand mentioned here."}, headers=alex)
    assert created.status_code == 200
    analysis_id = created.json()["analysis_id"]

    alex_history = [item["analysis_id"] for item in client.get("/api/v1/me/analyses", headers=alex).json()]
    blake_history = [item["analysis_id"] for item in client.get("/api/v1/me/analyses", headers=blake).json()]

    assert analysis_id in alex_history
    assert analysis_id not in blake_history
    assert client.get("/api/v1/me/analyses").status_code == 401


def test_owned_records_are_hidden_from_other_users_and_guests():
    _, alex, _ = make_user("alex")
    _, blake, _ = make_user("blake")
    analysis_id = client.post(
        "/check", json={"content": "No brand mentioned here."}, headers=alex
    ).json()["analysis_id"]

    assert client.get("/analyses/{}".format(analysis_id), headers=alex).status_code == 200
    assert client.get("/analyses/{}".format(analysis_id), headers=blake).status_code == 404
    assert client.get("/analyses/{}".format(analysis_id)).status_code == 404


def test_delete_requires_ownership():
    _, alex, _ = make_user("alex")
    _, blake, _ = make_user("blake")
    analysis_id = client.post(
        "/check", json={"content": "No brand mentioned here."}, headers=alex
    ).json()["analysis_id"]

    assert client.delete("/analyses/{}".format(analysis_id)).status_code == 401
    assert client.delete("/analyses/{}".format(analysis_id), headers=blake).status_code == 404
    assert client.get("/analyses/{}".format(analysis_id), headers=alex).status_code == 200
    assert client.delete("/analyses/{}".format(analysis_id), headers=alex).status_code == 200
    assert client.get("/analyses/{}".format(analysis_id)).status_code == 404