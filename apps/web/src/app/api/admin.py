"""Minimal read-only admin console API.

Guarded by the ADMIN_API_KEY environment variable; when it is unset the
endpoints are explicitly disabled (503) instead of silently open.
"""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from .store import list_analyses, list_feedback, list_reports

router = APIRouter()


def _require_admin(key: str) -> None:
    expected = os.getenv("ADMIN_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Admin API disabled (set ADMIN_API_KEY).")
    if not key or not hmac.compare_digest(key, expected):
        raise HTTPException(status_code=401, detail="Invalid admin key.")


@router.get("/admin/overview")
async def admin_overview(x_admin_key: str = Header(default="")):
    _require_admin(x_admin_key)
    analyses = list_analyses()
    feedback = list_feedback()
    reports = list_reports()
    scores = [item.get("risk_score") for item in analyses if isinstance(item.get("risk_score"), int)]
    return {
        "stats": {
            "analyses": len(analyses),
            "feedback": len(feedback),
            "reports": len(reports),
            "average_risk_score": round(sum(scores) / float(len(scores)), 1) if scores else None,
        },
        "feedback": feedback[:50],
        "reports": reports[:50],
        "recent_analyses": [
            {
                key: item.get(key)
                for key in (
                    "analysis_id",
                    "risk_score",
                    "risk_level",
                    "engine",
                    "score_kind",
                    "owner",
                    "created_at",
                )
            }
            for item in analyses[:20]
        ],
    }