"""LLM + RAG analysis endpoints powered by a local Ollama server.

Pipeline for ``POST /analyze``:
    1. Extract text signals and links from the submitted content.
    2. Retrieve the most relevant scam patterns from the local knowledge base
       with embeddings (RAG).
    3. Ask the local LLM for a structured risk assessment that is grounded in
       the retrieved context.
    4. Normalize the response, persist an analysis record and return it.

If Ollama is offline or returns garbage, the endpoint degrades to the same
deterministic heuristics used by ``/check`` so the product flow never breaks.

The endpoints are declared as sync ``def`` so FastAPI runs them in its worker
thread pool: slow LLM calls never block the event loop, and other frontend /
backend requests keep being served concurrently.
"""
from __future__ import annotations

import json
import re
from typing import List, Union
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from . import ollama_client, rag
from .auth import get_optional_user
from .check import (
    _build_summary,
    _risk_level_for_score,
    assess_content_heuristically,
    build_heuristic_record,
)
from .extraction import extract_emails, extract_links
from .store import create_analysis, utc_now_iso
from .url_analysis import analyze_urls

router = APIRouter()

_FENCE_PATTERN = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.S)


class AnalyzeRequest(BaseModel):
    content: str
    question: str = ""


class RagMatch(BaseModel):
    title: str
    category: str
    score: float
    text: str


class AnalyzeResult(BaseModel):
    schema_version: str = "2026-09-28"
    analysis_id: str
    assessment_status: str = "complete"
    risk_score: int
    risk_level: str
    score_kind: str
    scoring_version: str
    summary: str
    evidence: Union[str, List[str]]
    recommendation: Union[str, List[str]]
    created_at: str
    engine: str = "heuristic_fallback"
    llm_model: str = ""
    extracted_links: List[str] = []
    extracted_emails: List[str] = []
    rag_context: List[RagMatch] = []


class LlmHealth(BaseModel):
    status: str
    available: bool
    chat_model: str
    vision_model: str
    embed_model: str
    models: List[str] = []


def _parse_llm_json(raw: str) -> dict:
    """Parse the model reply into a dict, tolerating code fences."""
    text = (raw or "").strip()
    if not text:
        return {}
    text = _FENCE_PATTERN.sub("", text).strip()
    for candidate in (text, (_JSON_OBJECT_PATTERN.search(text).group(0) if _JSON_OBJECT_PATTERN.search(text) else "")):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _as_number(value) -> Union[int, float, None]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            return float(match.group(0))
    return None


def _normalize_llm_payload(parsed: dict, heuristic: dict, content: str) -> dict:
    """Coerce whatever the LLM returned into a well-formed analysis record."""
    score = _as_number(parsed.get("risk_score", parsed.get("score")))
    if score is None:
        score = heuristic["risk_score"]
    score = int(max(0, min(100, round(score))))
    risk_level = _risk_level_for_score(score)

    summary = str(parsed.get("summary") or "").strip()
    if not summary:
        evidence_text = heuristic["evidence_parts"]
        summary = _build_summary(" ".join(evidence_text), heuristic["recommendation"])

    evidence = parsed.get("evidence")
    if isinstance(evidence, list):
        evidence = [str(item).strip() for item in evidence if str(item).strip()]
        if not evidence:
            evidence = " ".join(heuristic["evidence_parts"]).strip()
    elif isinstance(evidence, str) and evidence.strip():
        evidence = evidence.strip()
    else:
        evidence = " ".join(heuristic["evidence_parts"]).strip()

    recommendation = str(parsed.get("recommendation") or "").strip()
    if not recommendation:
        recommendation = heuristic["recommendation"]

    return {
        "risk_score": score,
        "risk_level": risk_level,
        "summary": summary,
        "evidence": evidence,
        "recommendation": recommendation,
    }


def _build_prompt(
    content: str,
    question: str,
    links: List[str],
    emails: List[str],
    matches: List[dict],
    url_findings: List[dict] = None,
) -> str:
    lines = [
        "You are ScamSense, an assistant that decides whether a message, email",
        "or screenshot text is a scam. Score risk from 0 (clearly safe) to 100",
        "(certain scam). Base your reasoning on the retrieved scam patterns and",
        "on concrete signals inside the message itself.",
        "",
        "Return ONLY one JSON object with exactly these keys:",
        '"risk_score": integer between 0 and 100,',
        '"risk_level": one of "low", "caution", "suspicious", "high", "very_high",',
        '"summary": one or two sentences explaining the verdict,',
        '"evidence": JSON array of 2 to 4 short strings citing concrete signals,',
        '"recommendation": one actionable sentence for the recipient.',
        "",
        "Retrieved scam patterns from the knowledge base (reference material):",
    ]
    if matches:
        for index, match in enumerate(matches, 1):
            lines.append(
                "{}. [{}] {} - {} (similarity {:.2f})".format(
                    index,
                    match.get("category", "general"),
                    match.get("title", ""),
                    match.get("text", ""),
                    match.get("score", 0.0),
                )
            )
    else:
        lines.append("(none retrieved)")
    if links:
        lines.append("")
        lines.append("Links detected in the message: " + ", ".join(links))
    if url_findings:
        flagged = [
            "{} -> {}".format(item.get("url", ""), ", ".join(item.get("signals") or []))
            for item in url_findings
            if item.get("signals")
        ]
        if flagged:
            lines.append("Passive URL risk signals: " + "; ".join(flagged))
    if emails:
        lines.append("Email addresses detected: " + ", ".join(emails))
    if question:
        lines.append("")
        lines.append("Extra question from the user: " + question.strip())
    lines.append("")
    lines.append('Message to analyze:"""')
    lines.append(content)
    lines.append('"""')
    return "\n".join(lines)


def run_llm_analysis(content: str, question: str = "") -> dict:
    """Execute the extract -> RAG -> LLM pipeline and return a record."""
    links = extract_links(content)
    emails = extract_emails(content)
    url_scan = analyze_urls(links)
    heuristic = assess_content_heuristically(content)

    query = content.strip()
    if question and question.strip():
        query = "{}\n{}".format(query, question.strip())
    # Embeddings also run through Ollama, so skip retrieval when it is offline.
    matches = rag.retrieve(query, top_k=3) if ollama_client.is_available() else []

    record = {
        "schema_version": "2026-09-28",
        "analysis_id": str(uuid4()),
        "assessment_status": "complete",
        "created_at": utc_now_iso(),
        "extracted_links": links,
        "extracted_emails": emails,
        "owner": None,
        "rag_context": matches,
        "engine": "heuristic_fallback",
        "llm_model": "",
    }

    used_llm = False
    if ollama_client.is_available():
        try:
            prompt = _build_prompt(content, question, links, emails, matches, url_scan["results"])
            raw = ollama_client.generate(
                prompt,
                model=ollama_client.chat_model(),
                json_format=True,
                timeout=120.0,
            )
            parsed = _parse_llm_json(raw)
            if parsed:
                normalized = _normalize_llm_payload(parsed, heuristic, content)
                record.update(normalized)
                record["score_kind"] = "llm_rag_index"
                record["scoring_version"] = "ollama-{}+rag-1".format(ollama_client.chat_model())
                record["engine"] = "ollama_rag"
                record["llm_model"] = ollama_client.chat_model()
                used_llm = True
        except Exception:
            used_llm = False

    if not used_llm:
        fallback = build_heuristic_record(content)
        for key in (
            "risk_score",
            "risk_level",
            "score_kind",
            "scoring_version",
            "summary",
            "evidence",
            "recommendation",
        ):
            record[key] = fallback[key]
        record["engine"] = "heuristic_fallback"
        record["llm_model"] = ""

    return record


@router.post("/analyze", response_model=AnalyzeResult)
def analyze_with_llm(request: AnalyzeRequest, user: str = Depends(get_optional_user)):
    """Extract signals, retrieve RAG context and ask the local LLM."""
    record = run_llm_analysis(request.content or "", request.question or "")
    if user:
        record["owner"] = user
    create_analysis(record)
    return AnalyzeResult(**record)


@router.get("/llm/health", response_model=LlmHealth)
def llm_health():
    """Report local Ollama availability and configured models."""
    available = ollama_client.is_available()
    return LlmHealth(
        status="ok" if available else "offline",
        available=available,
        chat_model=ollama_client.chat_model(),
        vision_model=ollama_client.vision_model(),
        embed_model=ollama_client.embed_model(),
        models=ollama_client.list_models() if available else [],
    )