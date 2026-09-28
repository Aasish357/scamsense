"""User-submitted scam reports."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .auth import get_optional_user
from .store import append_report

router = APIRouter()


class ReportRequest(BaseModel):
    analysis_id: str = ""
    reason: str = "suspicious_content"
    message: str = ""


@router.post("/reports")
@router.post("/api/v1/reports")
async def submit_report(report: ReportRequest, user: Optional[str] = Depends(get_optional_user)):
    stored = append_report(user, report.analysis_id, report.reason, report.message)
    return {"msg": "Report submitted successfully!", "created_at": stored["created_at"]}