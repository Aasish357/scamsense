from __future__ import annotations

from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .auth import get_optional_user
from .brand import BRAND_REGISTRY
from .extraction import extract_links
from .store import create_analysis, utc_now_iso
from .url_analysis import BASE_URL_SCORE, analyze_urls

router = APIRouter()

_BRAND_CANDIDATES = ("ExampleBrand", "TestBrand", "TrustedCompany")


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


def assess_content_heuristically(content: str) -> dict:
    """Deterministic keyword/URL heuristics.

    Shared by the ``/check`` endpoint and as the offline fallback for the
    LLM + RAG ``/analyze`` pipeline when the local Ollama server is down.
    """
    risk_score = 0
    evidence_parts = []
    recommendation = ""

    for brand_name in _BRAND_CANDIDATES:
        if brand_name in content:
            if BRAND_REGISTRY.get(brand_name):
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

    # Passive lexical URL analysis: parse-only, never fetches. The suggested
    # score can raise (never lower) the risk determined above.
    links = extract_links(content)
    if links:
        scan = analyze_urls(links)
        for result in scan["results"]:
            if result["signals"]:
                evidence_parts.append(
                    "URL {} flagged: {}.".format(result["url"], "; ".join(result["signals"]))
                )
        if scan["score_delta"]:
            risk_score = min(95, max(risk_score, BASE_URL_SCORE + scan["score_delta"]))

    return {
        "risk_score": risk_score,
        "evidence_parts": evidence_parts,
        "recommendation": recommendation,
    }


def build_heuristic_record(content: str) -> dict:
    """Build a full analysis record from the deterministic heuristics."""
    assessment = assess_content_heuristically(content)
    evidence = " ".join(assessment["evidence_parts"]).strip()
    recommendation = assessment["recommendation"]
    score = assessment["risk_score"]
    return {
        "schema_version": "2026-09-28",
        "analysis_id": str(uuid4()),
        "assessment_status": "complete",
        "risk_score": score,
        "risk_level": _risk_level_for_score(score),
        "score_kind": "heuristic_index",
        "scoring_version": "local-1",
        "summary": _build_summary(evidence, recommendation),
        "evidence": evidence,
        "recommendation": recommendation,
        "created_at": utc_now_iso(),
        "owner": None,
    }


@router.post("/check", response_model=AnalysisResult)
async def analyze_content(request: CheckRequest, user: Optional[str] = Depends(get_optional_user)):
    content = request.content or ""
    analysis = build_heuristic_record(content)
    if user:
        analysis["owner"] = user
    create_analysis(analysis)
    return AnalysisResult(**analysis)