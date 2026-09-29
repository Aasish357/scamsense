"""HTTP endpoints for the email and QR-code analysis modalities.

Both reuse the shared extract -> RAG -> LLM pipeline in ``llm_analyze`` and
only add the modality-specific parsing step, so results stay comparable with
text and screenshot checks and land in the same history/reporting flow.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from .auth import get_optional_user
from .email_analysis import analyze_email
from .llm_analyze import AnalyzeResult, run_llm_analysis
from .rate_limit import enforce_rate_limit
from .qr_analysis import analyze_qr
from .screenshot import _validate_upload
from .store import create_analysis

router = APIRouter()

MAX_EMAIL_BYTES = 2 * 1024 * 1024


class EmailAnalyzeRequest(BaseModel):
    raw_email: str
    question: str = ""


class EmailPreview(BaseModel):
    subject: str = ""
    from_header: str = ""
    attachments: List[str] = []
    links: List[str] = []
    phones: List[str] = []


class EmailFindings(BaseModel):
    signals: List[str] = []
    score_delta: int = 0
    suggested_score: int = 0
    parsed: EmailPreview


def _email_findings_payload(result: dict) -> dict:
    parsed = result["parsed"]
    return {
        "signals": result["signals"],
        "score_delta": result["score_delta"],
        "suggested_score": result["suggested_score"],
        "parsed": {
            "subject": parsed["headers"].get("Subject", ""),
            "from_header": parsed["headers"].get("From", ""),
            "attachments": parsed["attachments"],
            "links": parsed["links"],
            "phones": parsed["phones"],
        },
    }


def _analyze_raw_email(raw_email: str, question: str, user) -> AnalyzeResult:
    raw_email = raw_email or ""
    if not raw_email.strip():
        raise HTTPException(
            status_code=400,
            detail="No email content. Paste the raw message (headers included) or upload a .eml file.",
        )
    if len(raw_email) > MAX_EMAIL_BYTES:
        raise HTTPException(status_code=413, detail="Email exceeds the 2 MB limit.")

    result = analyze_email(raw_email)
    content = "\n".join(
        part for part in (result["parsed"]["body"], raw_email) if part
    )
    record = run_llm_analysis(
        content,
        question,
        modality="email",
        extra_evidence=result["signals"],
        suggested_score=result["suggested_score"],
    )
    if user:
        record["owner"] = user
    record["email_findings"] = _email_findings_payload(result)
    create_analysis(record)
    return AnalyzeResult(**record)


@router.post("/analyze/email", response_model=AnalyzeResult)
def analyze_email_message(
    request: EmailAnalyzeRequest,
    user: str = Depends(get_optional_user),
    _rate_limit: None = Depends(enforce_rate_limit),
):
    """Analyze a pasted raw email (headers + body) through the LLM pipeline."""
    return _analyze_raw_email(request.raw_email, request.question, user)


@router.post("/analyze/email/upload", response_model=AnalyzeResult)
def analyze_email_upload(
    file: UploadFile = File(...),
    question: str = "",
    user: str = Depends(get_optional_user),
    _rate_limit: None = Depends(enforce_rate_limit),
):
    """Analyze an uploaded .eml / .txt message file."""
    payload = file.file.read() if file.file else b""
    if not payload:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(payload) > MAX_EMAIL_BYTES:
        raise HTTPException(status_code=413, detail="Email exceeds the 2 MB limit.")
    try:
        raw_email = payload.decode("utf-8")
    except UnicodeDecodeError:
        raw_email = payload.decode("utf-8", "ignore")
    if not any(character.isdigit() or character.isalpha() for character in raw_email):
        raise HTTPException(status_code=400, detail="File does not contain a readable email.")
    return _analyze_raw_email(raw_email, question or "", user)


@router.get("/analyze/email/findings", response_model=EmailFindings)
def email_findings_preview(raw_email: str = ""):
    """Header-level findings only, without running the LLM pipeline."""
    if not raw_email.strip():
        raise HTTPException(status_code=400, detail="Provide raw_email to inspect.")
    return EmailFindings(**_email_findings_payload(analyze_email(raw_email)))


@router.post("/analyze/qr", response_model=AnalyzeResult)
def analyze_qr_code(
    file: UploadFile = File(...),
    question: str = "",
    user: str = Depends(get_optional_user),
    _rate_limit: None = Depends(enforce_rate_limit),
):
    """Decode a QR code image locally and analyze the payload."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    image_data = file.file.read()
    _validate_upload(image_data)

    result = analyze_qr(image_data)
    if not result["payloads"]:
        raise HTTPException(
            status_code=422,
            detail="No QR code could be decoded from this image.",
        )

    record = run_llm_analysis(
        result["content"],
        question or "Analyze this QR code payload for scam signals",
        modality="qr",
        extra_evidence=result["signals"],
        suggested_score=result["suggested_score"],
    )
    if user:
        record["owner"] = user
    record["qr_payloads"] = result["payloads"]
    create_analysis(record)
    return AnalyzeResult(**record)