"""Tests for the public rate limiter."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi.testclient import TestClient

from apps.web.src.app.api import rate_limit
from apps.web.src.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_buckets():
    rate_limit.reset()
    yield
    rate_limit.reset()


def test_analysis_endpoints_are_rate_limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "3")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")

    codes = [
        client.post("/check", json={"content": "hello there"}).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [429, 429]


def test_rate_limited_response_is_actionable():
    os.environ["RATE_LIMIT_MAX_REQUESTS"] = "1"
    try:
        assert client.post("/check", json={"content": "one"}).status_code == 200
        limited = client.post("/check", json={"content": "two"})
        assert limited.status_code == 429
        assert "Too many analyses" in limited.json()["detail"]
        assert limited.headers.get("Retry-After")
    finally:
        os.environ.pop("RATE_LIMIT_MAX_REQUESTS", None)


def test_limit_is_per_client():
    os.environ["RATE_LIMIT_MAX_REQUESTS"] = "1"
    try:
        assert client.post(
            "/check", json={"content": "a"}, headers={"X-Forwarded-For": "203.0.113.10"}
        ).status_code == 200
        assert client.post(
            "/check", json={"content": "b"}, headers={"X-Forwarded-For": "203.0.113.10"}
        ).status_code == 429
        # A different caller is unaffected.
        assert client.post(
            "/check", json={"content": "c"}, headers={"X-Forwarded-For": "203.0.113.11"}
        ).status_code == 200
    finally:
        os.environ.pop("RATE_LIMIT_MAX_REQUESTS", None)


def test_cheap_reads_are_not_rate_limited():
    assert client.get("/health").status_code == 200
    assert client.get("/llm/health").status_code == 200
