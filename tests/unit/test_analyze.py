import json

from fastapi.testclient import TestClient

from apps.web.src.app.api import llm_analyze, ollama_client, rag
from apps.web.src.app.main import app

client = TestClient(app)

_RAG_MATCHES = [
    {
        "title": "Bank / payment-app impersonation phishing",
        "category": "phishing",
        "score": 0.73,
        "text": "Scammers impersonate a bank and claim the account is suspended.",
    }
]


def test_analyze_falls_back_to_heuristics_when_ollama_offline(monkeypatch):
    monkeypatch.setattr(ollama_client, "is_available", lambda *args, **kwargs: False)

    response = client.post(
        "/analyze",
        json={"content": "Please open http://example.com now."},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["engine"] == "heuristic_fallback"
    assert payload["llm_model"] == ""
    assert payload["score_kind"] == "heuristic_index"
    # A bare http:// link is a weak signal ("caution"), not "high" risk: the
    # evaluation harness showed the old 70-point placeholder flagged ordinary
    # messages, so scoring is now driven only by what a detector found.
    assert payload["risk_score"] == 45
    assert payload["risk_level"] == "caution"
    assert payload["extracted_links"] == ["http://example.com"]
    assert payload["rag_context"] == []

    stored = client.get("/analyses/{}".format(payload["analysis_id"]))
    assert stored.status_code == 200
    assert stored.json()["risk_score"] == 45


def test_analyze_uses_llm_and_rag_when_available(monkeypatch):
    llm_reply = {
        "risk_score": 42,
        "risk_level": "suspicious",
        "summary": "Suspicious link detected.",
        "evidence": ["Shortened link", "Urgency wording"],
        "recommendation": "Verify through official channels.",
    }
    monkeypatch.setattr(ollama_client, "is_available", lambda *args, **kwargs: True)
    monkeypatch.setattr(llm_analyze.rag, "retrieve", lambda query, top_k=3: list(_RAG_MATCHES))
    monkeypatch.setattr(
        ollama_client,
        "generate",
        lambda *args, **kwargs: json.dumps(llm_reply),
    )

    response = client.post(
        "/analyze",
        json={"content": "Urgent! Verify at http://fake-bank-login.xyz"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["engine"] == "ollama_rag"
    assert payload["score_kind"] == "llm_rag_index"
    assert "rag-1" in payload["scoring_version"]
    # The risk level is always re-derived from the score so badges stay consistent.
    assert payload["risk_score"] == 42
    assert payload["risk_level"] == "caution"
    assert payload["evidence"] == ["Shortened link", "Urgency wording"]
    assert payload["recommendation"] == "Verify through official channels."
    assert payload["rag_context"][0]["title"].startswith("Bank")
    assert payload["extracted_links"] == ["http://fake-bank-login.xyz"]

    stored = client.get("/analyses/{}".format(payload["analysis_id"]))
    assert stored.status_code == 200
    assert stored.json()["engine"] == "ollama_rag"


def test_analyze_recovers_when_llm_returns_garbage(monkeypatch):
    monkeypatch.setattr(ollama_client, "is_available", lambda *args, **kwargs: True)
    monkeypatch.setattr(llm_analyze.rag, "retrieve", lambda query, top_k=3: list(_RAG_MATCHES))
    monkeypatch.setattr(
        ollama_client,
        "generate",
        lambda *args, **kwargs: "sorry, I cannot help with that",
    )

    response = client.post(
        "/analyze",
        json={"content": "Please open http://example.com now."},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["engine"] == "heuristic_fallback"
    assert payload["score_kind"] == "heuristic_index"
    assert payload["risk_score"] == 45
    # RAG context is still reported even though the LLM failed.
    assert payload["rag_context"][0]["category"] == "phishing"


def test_analyze_parses_json_wrapped_in_code_fences(monkeypatch):
    llm_reply = {
        "risk_score": 90,
        "summary": "Phishing attempt.",
        "evidence": "Spoofed domain",
        "recommendation": "Do not click.",
    }
    fenced = "```json\n{}\n```".format(json.dumps(llm_reply))
    monkeypatch.setattr(ollama_client, "is_available", lambda *args, **kwargs: True)
    monkeypatch.setattr(llm_analyze.rag, "retrieve", lambda query, top_k=3: [])
    monkeypatch.setattr(ollama_client, "generate", lambda *args, **kwargs: fenced)

    response = client.post("/analyze", json={"content": "short message"})
    assert response.status_code == 200

    payload = response.json()
    assert payload["engine"] == "ollama_rag"
    assert payload["risk_score"] == 90
    assert payload["risk_level"] == "very_high"
    assert payload["evidence"] == "Spoofed domain"


def test_rag_retrieval_ranks_most_similar_document_first(monkeypatch):
    def fake_embed(text, **kwargs):
        lowered = (text or "").lower()
        if "impersonate a bank" in lowered:
            return [1.0, 0.0]
        if "won a lottery" in lowered:
            return [0.0, 1.0]
        return [0.1, 0.1]

    rag.reset_cache()
    monkeypatch.setattr(ollama_client, "embed", fake_embed)
    try:
        results = rag.retrieve("they impersonate a bank and suspend the account", top_k=2)
    finally:
        rag.reset_cache()

    assert len(results) == 2
    assert results[0]["title"].startswith("Bank")
    assert results[0]["score"] > results[1]["score"]
    assert {"title", "category", "text", "score"} <= set(results[0].keys())


def test_screenshot_endpoint_returns_links_and_method(monkeypatch):
    from apps.web.src.app.api import screenshot as screenshot_module

    # Pin the environment: neither OCR nor the local vision model is assumed.
    monkeypatch.setattr(screenshot_module, "_ocr_with_tesseract", lambda data: "")
    monkeypatch.setattr(screenshot_module, "_transcribe_with_vision", lambda data: "")

    from base64 import b64decode
    from io import BytesIO

    sample_png = b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4//8/AwAI/AL+X4n3NwAAAABJRU5ErkJggg=="
    )
    response = client.post(
        "/screenshot",
        files={"file": ("sample.png", BytesIO(sample_png), "image/png")},
    )
    assert response.status_code == 200

    payload = response.json()
    # Nothing is readable in a 1x1 PNG and no OCR/vision engine is available
    # here, so the endpoint must say so rather than invent placeholder text.
    assert payload["extraction_method"] == "unavailable"
    assert payload["extracted_text"] == ""
    assert payload["links"] == []
    assert payload["warnings"], "an unreadable image must produce an explicit warning"


def test_llm_health_endpoint_reports_configuration():
    response = client.get("/llm/health")
    assert response.status_code == 200

    payload = response.json()
    assert set(payload.keys()) >= {
        "status",
        "available",
        "chat_model",
        "vision_model",
        "embed_model",
        "models",
    }
    assert payload["status"] in ("ok", "offline")
    assert payload["available"] == (payload["status"] == "ok")