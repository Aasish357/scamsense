from __future__ import annotations

from uuid import uuid4
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .auth import get_optional_user
from .rate_limit import enforce_rate_limit
from .brand import BRAND_REGISTRY
from .extraction import extract_links
from .phone_analysis import PHONE_BASE_SCORE, analyze_phones
from .store import create_analysis, utc_now_iso
from .text_signals import BASE_TEXT_SCORE, analyze_text_signals
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
    modality: str = "text"


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
    """Deterministic detectors, shared by ``/check`` and the offline LLM fallback.

    Scoring is **detector-driven**: the base index reflects only what a detector
    actually found. Message length and the mere presence of a link are not risk
    signals - the evaluation harness (``scripts/evaluate.py``) showed the
    earlier placeholder rules scoring 41% of benign messages as suspicious, so
    they were removed in favour of honest, evidence-linked scores.
    """
    risk_score = 0
    evidence_parts = []
    recommendation = ""

    for brand_name in _BRAND_CANDIDATES:
        if brand_name in content:
            if BRAND_REGISTRY.get(brand_name):
                evidence_parts.append("Trusted brand detected.")
            else:
                risk_score = max(risk_score, 50)
                evidence_parts.append("Untrusted brand detected.")
            break

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
            recommendation = "Verify the link before clicking it."
        else:
            evidence_parts.append(
                "Link structure looks ordinary ({} link(s) found).".format(len(links))
            )

    # Phone number signals: premium-rate lines, brand/country mismatch,
    # messaging-app routing and pressure to call back.
    phone_scan = analyze_phones(content)
    for result in phone_scan["results"]:
        if result["signals"]:
            evidence_parts.append(
                "Phone {} flagged: {}.".format(result["number"], "; ".join(result["signals"]))
            )
    if phone_scan["score_delta"]:
        risk_score = min(95, max(risk_score, PHONE_BASE_SCORE + phone_scan["score_delta"]))
        recommendation = "Do not call back until you verify the number on the official site."

    # Payment URIs (upi://, bitcoin:) and tel: links are neither URLs nor
    # dialable numbers, so they need their own pass over the raw text.
    text_scan = analyze_text_signals(content)
    for signal in text_scan["signals"]:
        evidence_parts.append("Text signal: {}.".format(signal))
    if text_scan["score_delta"]:
        risk_score = min(95, max(risk_score, BASE_TEXT_SCORE + text_scan["score_delta"]))
        recommendation = "Do not scan or pay until you verify it inside the official app."

    if risk_score == 0 and not evidence_parts:
        evidence_parts.append("No notable risk signals detected.")
        recommendation = "No immediate action required."

    return {
        "risk_score": risk_score,
        "evidence_parts": evidence_parts,
        "recommendation": recommendation,
    }


def build_heuristic_record(
    content: str,
    extra_evidence: Optional[List[str]] = None,
    suggested_score: Optional[int] = None,
    modality: str = "text",
) -> dict:
    """Build a full analysis record from the deterministic heuristics.

    ``extra_evidence`` lets modality-specific analyzers (email headers, QR
    payloads) contribute their findings, and ``suggested_score`` raises (never
    lowers) the score when those signals are strong on their own.
    """
    assessment = assess_content_heuristically(content)
    evidence_parts = list(assessment["evidence_parts"])
    evidence_parts.extend(item for item in (extra_evidence or []) if item)
    evidence = " ".join(evidence_parts).strip()
    recommendation = assessment["recommendation"]
    score = assessment["risk_score"]
    if suggested_score:
        score = min(95, max(score, int(suggested_score)))
    return {
        "schema_version": "2026-09-28",
        "analysis_id": str(uuid4()),
        "assessment_status": "complete",
        "risk_score": score,
        "risk_level": _risk_level_for_score(score),
        "score_kind": "heuristic_index",
        "scoring_version": "local-2",
        "summary": _build_summary(evidence, recommendation),
        "evidence": evidence,
        "recommendation": recommendation,
        "created_at": utc_now_iso(),
        "owner": None,
        "modality": modality,
    }


@router.post("/check", response_model=AnalysisResult)
async def analyze_content(
    request: CheckRequest,
    user: Optional[str] = Depends(get_optional_user),
    _rate_limit: None = Depends(enforce_rate_limit),
):
    content = request.content or ""
    analysis = build_heuristic_record(content)
    if user:
        analysis["owner"] = user
    create_analysis(analysis)
    return AnalysisResult(**analysis)