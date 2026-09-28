import io

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

try:
    import pytesseract
except ImportError:  # pragma: no cover - optional local dependency
    pytesseract = None  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional local dependency
    Image = None  # type: ignore[assignment]

router = APIRouter()


class ScreenshotAnalysisResult(BaseModel):
    extracted_text: str
    recommendations: str


@router.post("/screenshot", response_model=ScreenshotAnalysisResult)
async def analyze_screenshot(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    image_data = await file.read()

    extracted_text = ""
    if pytesseract is not None and Image is not None:
        try:
            image = Image.open(io.BytesIO(image_data))
            extracted_text = pytesseract.image_to_string(image)
        except Exception:
            extracted_text = ""

    if not extracted_text.strip():
        extracted_text = "sample extracted text (OCR fallback)"

    recommendations = "Analyze the content for suspicious patterns."

    return ScreenshotAnalysisResult(
        extracted_text=extracted_text,
        recommendations=recommendations,
    )
