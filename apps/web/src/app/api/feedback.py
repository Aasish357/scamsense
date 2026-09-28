import os

from fastapi import APIRouter
from pydantic import BaseModel

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover - optional local dependency
    Client = object  # type: ignore[assignment]
    create_client = None  # type: ignore[assignment]

from .store import append_feedback

router = APIRouter()


class Feedback(BaseModel):
    username: str
    message: str


def get_supabase():
    if create_client is None:
        return None
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


@router.post("/feedback")
async def submit_feedback(feedback: Feedback):
    supabase = get_supabase()
    if supabase is not None:
        supabase.table("feedback").insert(
            {
                "username": feedback.username,
                "message": feedback.message,
            }
        ).execute()
        return {"msg": "Feedback submitted successfully!"}

    append_feedback(feedback.username, feedback.message)
    return {"msg": "Feedback submitted successfully!"}
