import base64
import json
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from apps.web.src.app.api import llm_analyze, ollama_client
from apps.web.src.app.api.email_analysis import analyze_email, parse_email
from apps.web.src.app.api.extraction import extract_phone_numbers
from apps.web.src.app.api.phone_analysis import analyze_phones
from apps.web.src.app.api.qr_analysis import analyze_qr, decode_qr_payloads
from apps.web.src.app.main import app

client = TestClient(app)

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4//8/AwAI/AL+X4n3NwAAAABJRU5ErkJggg=="
)

SPAM_EMAIL = """From: "PayPal Security Center" <service@paypal-verify-account.top>
Reply-To: reply@fastmail-drop.ru
Return-Path: <bounce@bulk-sender-98.ru>
Date: Mon, 28 Sep 2026 10:00:00 +0000
Message-ID: <12345@paypal-verify-account.top>
Subject: Your account will be limited - verify now
Authentication-Results: mx.example.com; spf=fail smtp.mailfrom=bulk-sender-98.ru; dkim=pass header.d=bulk-sender-98.ru; dmarc=fail action=temprelax
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/plain; charset="utf-8"

Dear customer, your PayPal account will be limited within 24 hours.
Verify immediately: http://paypal-verify-account.top/login
Support line: +92 300 1234567
--BOUNDARY
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="Invoice_Security.exe"
Content-Transfer-Encoding: base64

TVdTClRoaXMgaXMgbm90IGEgcmVhbCBmaWxlLgo=
--BOUNDARY--
"""

CLEAN_EMAIL = """From: Anna <anna@example.com>
To: team@example.com
Date: Mon, 28 Sep 2026 09:00:00 +0000
Message-ID: <999@example.com>
Subject: Sprint notes
Authentication-Results: mx.example.com; spf=pass smtp.mailfrom=example.com; dkim=pass header.d=example.com; dmarc=pass
Received: from mail.example.com (mail.example.com [198.51.100.7])
	by mx.example.net with ESMTPS id 4A2F; Mon, 28 Sep 2026 09:00:01 +0000

Here are the notes for this week. See you at the standup tomorrow.
"""


def _offline(monkeypatch):
    monkeypatch.setattr(ollama_client, "is_available", lambda *args, **kwargs: False)


# --- phone numbers ----------------------------------------------------------


def test_phone_extraction_keeps_country_codes_and_ignores_noise():
    numbers = extract_phone_numbers(
        "Call +91 90000 00000 or 1-800-555-0199 now. Price is 1234567 and year 2026."
    )
    assert "+919000000000" in numbers
    assert "18005550199" in numbers
    assert "1234567" not in numbers
    assert "2026" not in numbers


def test_premium_rate_number_is_flagged():
    result = analyze_phones("Dial 1-900-555-0199 right now to claim your prize")
    joined = " | ".join(signal for item in result["results"] for signal in item["signals"])
    assert "premium-rate" in joined
    assert result["score_delta"] >= 35


def test_brand_and_country_mismatch_is_flagged():
    result = analyze_phones(
        "URGENT: your PayPal account is blocked. Call us immediately on +91 90000 00000 "
        "(WhatsApp only)."
    )
    joined = " | ".join(signal for item in result["results"] for signal in item["signals"])
    assert "paypal" in joined
    assert "messaging app" in joined
    assert result["score_delta"] == 60


def test_real_support_number_stays_clean():
    result = analyze_phones(
        "Your order ships tomorrow. Contact +1 415 555 2671 if you have questions."
    )
    assert result["score_delta"] == 0
    assert result["numbers"] == ["+14155552671"]


def test_check_endpoint_surfaces_phone_signals():
    response = client.post(
        "/check",
        json={
            "content": "URGENT: your PayPal account is blocked. Call +91 90000 00000 "
            "immediately (WhatsApp)."
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "Phone +919000000000 flagged" in payload["evidence"]
    assert payload["risk_score"] >= 60


# --- email headers ----------------------------------------------------------


def test_parse_email_reads_headers_body_and_attachments():
    parsed = parse_email(SPAM_EMAIL)
    assert parsed["headers"]["Subject"].startswith("Your account will be limited")
    assert parsed["attachments"] == ["Invoice_Security.exe"]
    assert parsed["links"] == ["http://paypal-verify-account.top/login"]
    assert parsed["phones"] == ["+923001234567"]
    assert "limited within 24 hours" in parsed["body"]


def test_authentication_failures_and_spoofing_are_flagged():
    result = analyze_email(SPAM_EMAIL)
    joined = " | ".join(result["signals"])
    assert "SPF authentication failed" in joined
    assert "DMARC authentication failed" in joined
    assert "Reply-To" in joined
    assert "Return-Path" in joined
    assert "display name claims 'paypal'" in joined
    assert "dangerous attachment (Invoice_Security.exe)" in joined
    assert result["score_delta"] >= 90
    assert result["suggested_score"] >= 90


def test_clean_email_produces_no_strong_findings():
    result = analyze_email(CLEAN_EMAIL)
    joined = " | ".join(result["signals"])
    assert "authentication failed" not in joined
    assert "display name claims" not in joined
    assert result["suggested_score"] == 0


def test_analyze_email_endpoint_reports_modality_and_evidence(monkeypatch):
    _offline(monkeypatch)
    response = client.post("/analyze/email", json={"raw_email": SPAM_EMAIL})
    assert response.status_code == 200

    payload = response.json()
    assert payload["modality"] == "email"
    assert payload["engine"] == "heuristic_fallback"
    assert payload["risk_score"] >= 85
    assert payload["risk_level"] == "very_high"
    assert "DMARC authentication failed" in payload["evidence"]
    assert payload["extracted_phones"] == ["+923001234567"]

    stored = client.get("/analyses/{}".format(payload["analysis_id"]))
    assert stored.status_code == 200
    assert stored.json()["modality"] == "email"


def test_analyze_email_accepts_eml_upload(monkeypatch):
    _offline(monkeypatch)
    response = client.post(
        "/analyze/email/upload",
        files={"file": ("scam.eml", BytesIO(SPAM_EMAIL.encode("utf-8")), "message/rfc822")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["modality"] == "email"
    assert "dangerous attachment" in payload["evidence"]


def test_analyze_email_rejects_empty_content():
    response = client.post("/analyze/email", json={"raw_email": "   "})
    assert response.status_code == 400


def test_email_findings_preview_runs_without_llm():
    response = client.get("/analyze/email/findings", params={"raw_email": SPAM_EMAIL})
    assert response.status_code == 200
    payload = response.json()
    assert payload["score_delta"] >= 90
    assert payload["parsed"]["subject"].startswith("Your account will be limited")
    assert payload["parsed"]["attachments"] == ["Invoice_Security.exe"]


# --- QR codes ---------------------------------------------------------------

cv2 = pytest.importorskip("cv2", reason="opencv-python-headless is not installed")

SUSPICIOUS_QR_TEXT = "http://free-prize-claim.top/verify"


def _qr_png(text):
    matrix = cv2.QRCodeEncoder_create().encode(text)
    ok, buffer = cv2.imencode(".png", matrix)
    assert ok
    return buffer.tobytes()


def test_qr_payloads_round_trip():
    assert decode_qr_payloads(_qr_png(SUSPICIOUS_QR_TEXT)) == [SUSPICIOUS_QR_TEXT]


def test_suspicious_qr_link_is_scored_with_url_signals():
    result = analyze_qr(_qr_png(SUSPICIOUS_QR_TEXT))
    joined = " | ".join(result["signals"])
    assert "QR link" in joined
    assert "suspicious TLD" in joined
    assert result["suggested_score"] >= 70


def test_payment_qr_payload_is_flagged():
    result = analyze_qr(_qr_png("upi://pay?pa=scammer@bank&am=5000&cu=INR"))
    assert any("payment QR payload (upi)" in signal for signal in result["signals"])
    assert result["suggested_score"] >= 70


def test_analyze_qr_endpoint_analyzes_decoded_payload(monkeypatch):
    _offline(monkeypatch)
    response = client.post(
        "/analyze/qr",
        files={"file": ("qr.png", BytesIO(_qr_png(SUSPICIOUS_QR_TEXT)), "image/png")},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["modality"] == "qr"
    assert payload["risk_score"] >= 70
    assert SUSPICIOUS_QR_TEXT in payload["extracted_links"]
    assert "QR link" in payload["evidence"]


def test_analyze_qr_rejects_image_without_a_code():
    response = client.post(
        "/analyze/qr",
        files={"file": ("blank.png", BytesIO(TINY_PNG), "image/png")},
    )
    assert response.status_code == 422
    assert "No QR code" in response.json()["detail"]


def test_screenshot_endpoint_decodes_embedded_qr_codes():
    response = client.post(
        "/screenshot",
        files={"file": ("qr.png", BytesIO(_qr_png(SUSPICIOUS_QR_TEXT)), "image/png")},
    )
    assert response.status_code == 200

    payload = response.json()
    assert "qr_decode" in payload["extraction_method"]
    assert payload["qr_payloads"] == [SUSPICIOUS_QR_TEXT]
    assert payload["links"] == [SUSPICIOUS_QR_TEXT]


# --- modality plumbing ------------------------------------------------------


def test_analyze_endpoint_accepts_modality_hint(monkeypatch):
    _offline(monkeypatch)
    response = client.post(
        "/analyze",
        json={"content": "Urgent! Verify at http://fake-bank-login.xyz", "modality": "screenshot"},
    )
    assert response.status_code == 200
    assert response.json()["modality"] == "screenshot"


def test_analyze_endpoint_defaults_unknown_modality_to_text(monkeypatch):
    _offline(monkeypatch)
    response = client.post(
        "/analyze", json={"content": "hello there", "modality": "not-a-modality"}
    )
    assert response.status_code == 200
    assert response.json()["modality"] == "text"


def test_email_findings_are_kept_when_the_llm_answers(monkeypatch):
    monkeypatch.setattr(ollama_client, "is_available", lambda *a, **k: True)
    monkeypatch.setattr(llm_analyze.rag, "retrieve", lambda query, top_k=3: [])
    monkeypatch.setattr(
        ollama_client,
        "generate",
        lambda *a, **k: json.dumps(
            {
                "risk_score": 88,
                "summary": "Spoofed sender.",
                "evidence": ["Lookalike domain"],
                "recommendation": "Do not click.",
            }
        ),
    )

    response = client.post("/analyze/email", json={"raw_email": SPAM_EMAIL})
    assert response.status_code == 200

    payload = response.json()
    assert payload["engine"] == "ollama_rag"
    assert payload["modality"] == "email"
    # The deterministic header findings stay visible even though the model
    # produced its own evidence list.
    assert payload["evidence"][0].startswith("SPF authentication failed")
    assert "Lookalike domain" in payload["evidence"]


# --- regression tests for edge cases found during the robustness pass ------


def test_parenthesised_phone_formats_are_extracted():
    assert extract_phone_numbers("Dial +1 (415) 555-2671 today") == ["+14155552671"]
    assert extract_phone_numbers("(415) 555-2671") == ["4155552671"]
    assert extract_phone_numbers("Reach us: 020 7946 0958") == ["02079460958"]


def test_order_ids_are_not_treated_as_cheap_phone_numbers():
    result = analyze_phones("Order 12345678 shipped to ZIP 90210")
    assert result["numbers"] == ["12345678"]
    assert result["score_delta"] == 0


def test_body_only_paste_invents_no_header_findings():
    result = analyze_email("hey, are we still meeting tomorrow for coffee?")
    assert result["signals"] == []
    assert result["suggested_score"] == 0
    assert analyze_email("")["signals"] == []


def test_header_only_message_reports_structure_without_driving_the_score():
    result = analyze_email("From: a@b.com\nSubject: hi\n")
    assert "missing Message-ID header" in result["signals"]
    # Structural gaps alone must never push a forwarded email into high risk.
    assert result["suggested_score"] == 0
