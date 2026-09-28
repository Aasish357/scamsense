from fastapi import APIRouter, HTTPException

from .store import delete_analysis, get_analysis, list_analyses

router = APIRouter()


@router.get("/analyses/{analysis_id}")
@router.get("/api/v1/analyses/{analysis_id}")
async def read_analysis(analysis_id: str):
    analysis = get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return analysis


@router.delete("/analyses/{analysis_id}")
@router.delete("/api/v1/analyses/{analysis_id}")
async def remove_analysis(analysis_id: str):
    if not delete_analysis(analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return {"analysis_id": analysis_id, "deleted": True}


@router.get("/api/v1/me/analyses")
@router.get("/me/analyses")
async def read_my_analyses():
    return list_analyses()
