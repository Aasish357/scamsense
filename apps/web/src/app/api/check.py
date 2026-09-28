from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from .brand import verify_brand
from .store import create_analysis, utc_now_iso

router = APIRouter()


class CheckRequest(BaseModel):
    content: str


class AnalysisResult(BaseModel):
    schema_version: str = "2026-09-28"
    analysis_id: str
    assessment_status: str = "complete"
    risk_score: int
    risk_level: str
    score_kind: str = "heuristic_index"
    scoring_version: str = "local-1"
    summary: str
    evidence: str
    recommendation: str
    created_at: str


def _risk_level_for_score(score: int) -> str:
    if score >= 85:
        return "very_high"
    if score >= 70:
        return "high"
    if score >= 50:
        return "suspicious"
    if score >= 20:
        return "caution"
    return "low"


def _build_summary(evidence: str, recommendation: str) -> str:
    evidence = evidence.strip()
    recommendation = recommendation.strip()
    if evidence and recommendation:
        return f"{evidence} {recommendation}"
    return evidence or recommendation or "No notable risk signals detected."


@router.post("/check", response_model=AnalysisResult)
async def analyze_content(request: CheckRequest):
    content = request.content or ""
    risk_score = 0
    evidence_parts = []
    recommendation = ""

    for brand_name in ("ExampleBrand", "TestBrand", "TrustedCompany"):
        if brand_name in content:
            brand_check = await verify_brand(brand_name)
            if brand_check.verified:
                risk_score += 10
                evidence_parts.append("Trusted brand detected.")
            else:
                risk_score += 50
                evidence_parts.append("Untrusted brand detected.")
            break

    if len(content) > 100:
        risk_score = max(risk_score, 50)
        evidence_parts.append("Content length suggests caution.")
        recommendation = "Consider shortening the message."
    elif "http" in content:
        risk_score = max(risk_score, 70)
        evidence_parts.append("Detected a URL in the content.")
        recommendation = "Verify the URL before clicking."
    else:
        risk_score = max(risk_score, 0)
        evidence_parts.append("Content appears to be normal text.")
        recommendation = "No immediate action required."

    evidence = " ".join(evidence_parts).strip()
    created_at = utc_now_iso()
    analysis = {
        "schema_version": "2026-09-28",
        "analysis_id": str(uuid4()),
        "assessment_status": "complete",
        "risk_score": risk_score,
        "risk_level": _risk_level_for_score(risk_score),
        "score_kind": "heuristic_index",
        "scoring_version": "local-1",
        "summary": _build_summary(evidence, recommendation),
        "evidence": evidence,
        "recommendation": recommendation,
        "created_at": created_at,
    }
    create_analysis(analysis)
    return AnalysisResult(**analysis)
