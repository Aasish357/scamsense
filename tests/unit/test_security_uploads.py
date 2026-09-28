from base64 import b64decode
from io import BytesIO

from fastapi.testclient import TestClient

from apps.web.src.app.api.screenshot import MAX_UPLOAD_BYTES
from apps.web.src.app.main import app

client = TestClient(app)

_SAMPLE_PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4//8/AwAI/AL+X4n3NwAAAABJRU5ErkJggg=="
)


def test_rejects_non_image_content_type():
    response = client.post(
        "/screenshot", files={"file": ("x.png", BytesIO(_SAMPLE_PNG), "text/plain")}
    )
    assert response.status_code == 400


def test_rejects_fake_signature_even_with_image_content_type():
    response = client.post(
        "/screenshot", files={"file": ("evil.png", BytesIO(b"not really an image"), "image/png")}
    )
    assert response.status_code == 400
    assert "signature" in response.json()["detail"].lower()


def test_rejects_oversized_upload():
    payload = b"\x89PNG\r\n\x1a\n" + b"0" * (MAX_UPLOAD_BYTES + 1)
    response = client.post(
        "/screenshot", files={"file": ("big.png", BytesIO(payload), "image/png")}
    )
    assert response.status_code == 413


def test_accepts_valid_png_signature():
    response = client.post(
        "/screenshot", files={"file": ("ok.png", BytesIO(_SAMPLE_PNG), "image/png")}
    )
    assert response.status_code == 200
    assert response.json()["extracted_text"]