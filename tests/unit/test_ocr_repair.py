"""OCR link repair: Tesseract shreds URLs, which would hide the scam."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from apps.web.src.app.api import screenshot as screenshot_module
from apps.web.src.app.api.ocr_repair import repair_urls
from apps.web.src.app.api.url_analysis import analyze_url
from apps.web.src.app.main import app

client = TestClient(app)

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
    b"\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.parametrize(
    "damaged, expected",
    [
        (
            "Verify now at: http: //paypal-verrify-accout. example login",
            "Verify now at: http://paypal-verrify-accout.example/login",
        ),
        (
            "See h t t p s : / / x. top / go",
            "See http://x.top",
        ),
        (
            "Pay now at http//192.0.2.44/pay/now ok",
            "Pay now at http://192.0.2.44/pay/now",
        ),
    ],
)
def test_damaged_links_are_rebuilt(damaged, expected):
    repaired, recovered = repair_urls(damaged)
    assert repaired == expected
    assert recovered and recovered[0].startswith("http://")


@pytest.mark.parametrize(
    "text",
    [
        "Check http://free-prize-claim.example/verify now",
        "No links here at all.",
        "Call 1-800-555-0199 today",
        "Two links: http://x.top/a and https://ok.example/b",
    ],
)
def test_intact_text_is_left_alone(text):
    repaired, recovered = repair_urls(text)
    assert repaired == text
    assert recovered == []


def test_repaired_link_is_analysable():
    """The point of the repair: the risk engine must be able to see the link."""
    damaged = "Verify now at: http: //paypal-verify-accout. example login"
    repaired, _ = repair_urls(damaged)
    assert analyze_url("http://paypal-verify-accout.example/login")["signals"], (
        "a repaired phishing link must still be flagged"
    )
    assert "paypal-verify-accout.example/login" in repaired


def test_screenshot_repairs_links_and_discloses_them(monkeypatch):
    monkeypatch.setattr(
        screenshot_module,
        "_ocr_with_tesseract",
        lambda data: "Your account is limited. Verify: http: //paypal-verify. example login",
    )
    monkeypatch.setattr(screenshot_module, "_transcribe_with_vision", lambda data: "")

    response = client.post(
        "/screenshot", files={"file": ("shot.png", BytesIO(TINY_PNG), "image/png")}
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["extraction_method"] == "tesseract_ocr"
    assert "http://paypal-verify.example/login" in payload["extracted_text"]
    assert payload["recovered_links"] == ["http://paypal-verify.example/login"]
    # The rebuilt link is a real link, so the extractor finds it.
    assert "http://paypal-verify.example/login" in payload["links"]
