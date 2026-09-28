"""Screenshot content extraction.

Extraction chain:
    1. Tesseract OCR when the binary is installed (pytesseract + Pillow).
    2. Local Ollama vision model (moondream by default) to transcribe or
       describe the image - no external API, runs fully on device.
    3. Deterministic fallback string so the flow never hard-fails.

Links found inside the extracted text are returned alongside it so the LLM
analysis pipeline can reason about them.
"""
import base64
import io
import re
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from . import ollama_client
from .extraction import extract_links

try:
    import pytesseract
except ImportError:  # pragma: no cover - optional local dependency
    pytesseract = None  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional local dependency
    Image = None  # type: ignore[assignment]

router = APIRouter()

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_DIMENSION = 10000
MAX_IMAGE_PIXELS = 40 * 1000 * 1000

# Uploads are validated by magic bytes, never by file extension or the
# client-supplied content type alone.
_SIGNATURES = (
    ("png", b"\x89PNG\r\n\x1a\n"),
    ("jpeg", b"\xff\xd8\xff"),
    ("gif", b"GIF87a"),
    ("gif", b"GIF89a"),
    ("bmp", b"BM"),
    ("webp", b"RIFF"),
)

# Real screenshots are far larger than this; tiny images (test fixtures,
# tracking pixels) skip the vision model to keep responses fast.
VISION_MIN_BYTES = 1024

# moondream answers reliably only to short, plain question-style prompts;
# complex instructions make it return empty output, so we try a small chain.
_VISION_PROMPTS = (
    "What does the text in this image say?",
    "Describe this image.",
)
_BBOX_PATTERN = re.compile(r"^\s*\[\s*\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)+\s*\]\s*$")


class ScreenshotAnalysisResult(BaseModel):
    extracted_text: str
    recommendations: str
    links: List[str] = []
    extraction_method: str = "fallback"


def _detect_image_format(image_data: bytes) -> str:
    for name, signature in _SIGNATURES:
        if image_data.startswith(signature):
            if name == "webp" and image_data[8:12] != b"WEBP":
                continue
            return name
    return ""


def _validate_upload(image_data: bytes) -> None:
    if not image_data:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(image_data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 8 MB upload limit.")
    if not _detect_image_format(image_data):
        raise HTTPException(
            status_code=400,
            detail="File signature is not a supported image (PNG, JPEG, GIF, BMP, WEBP).",
        )
    if Image is not None:
        try:
            with Image.open(io.BytesIO(image_data)) as probe:
                width, height = probe.size
        except Exception:
            raise HTTPException(status_code=400, detail="Image could not be decoded.")
        if (
            width > MAX_IMAGE_DIMENSION
            or height > MAX_IMAGE_DIMENSION
            or width * height > MAX_IMAGE_PIXELS
        ):
            raise HTTPException(status_code=413, detail="Image dimensions exceed the allowed limits.")


def _ocr_with_tesseract(image_data: bytes) -> str:
    if pytesseract is None or Image is None:
        return ""
    try:
        image = Image.open(io.BytesIO(image_data))
        return (pytesseract.image_to_string(image) or "").strip()
    except Exception:
        return ""


def _transcribe_with_vision(image_data: bytes) -> str:
    if len(image_data) < VISION_MIN_BYTES:
        return ""
    if not ollama_client.is_available():
        return ""
    image_b64 = base64.b64encode(image_data).decode("ascii")
    for prompt in _VISION_PROMPTS:
        try:
            candidate = ollama_client.generate(
                prompt,
                model=ollama_client.vision_model(),
                images=[image_b64],
                timeout=90.0,
            )
        except Exception:
            candidate = ""
        candidate = (candidate or "").strip()
        # Reject empty answers and raw bounding-box replies from the model.
        if candidate and not _BBOX_PATTERN.match(candidate):
            return candidate
    return ""


@router.post("/screenshot", response_model=ScreenshotAnalysisResult)
def analyze_screenshot(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    image_data = file.file.read()
    _validate_upload(image_data)

    extracted_text = _ocr_with_tesseract(image_data)
    method = "tesseract_ocr" if extracted_text else ""

    if not extracted_text:
        extracted_text = _transcribe_with_vision(image_data)
        method = "ollama_vision" if extracted_text else ""

    if not extracted_text:
        extracted_text = "sample extracted text (OCR fallback)"
        method = "fallback"

    recommendations = "Analyze the content for suspicious patterns."

    return ScreenshotAnalysisResult(
        extracted_text=extracted_text,
        recommendations=recommendations,
        links=extract_links(extracted_text),
        extraction_method=method,
    )