from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from .auth import get_optional_user, require_user
from .store import delete_analysis, get_analysis, list_analyses

router = APIRouter()


@router.get("/analyses/{analysis_id}")
@router.get("/api/v1/analyses/{analysis_id}")
async def read_analysis(
    analysis_id: str,
    user: Optional[str] = Depends(get_optional_user),
):
    analysis = get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    # Owned records are visible only to their owner; guest records (owner null)
    # remain readable by anyone holding the analysis id.
    owner = analysis.get("owner")
    if owner and owner != user:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return analysis


@router.delete("/analyses/{analysis_id}")
@router.delete("/api/v1/analyses/{analysis_id}")
async def remove_analysis(
    analysis_id: str,
    user: str = Depends(require_user),
):
    if not delete_analysis(analysis_id, owner=user):
        # 404 for both "missing" and "not yours" to avoid record enumeration.
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return {"analysis_id": analysis_id, "deleted": True}


@router.get("/api/v1/me/analyses")
@router.get("/me/analyses")
async def read_my_analyses(user: str = Depends(require_user)):
    return list_analyses(owner=user)