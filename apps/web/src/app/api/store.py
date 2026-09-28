from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List, Optional

try:
    from supabase import create_client
except ImportError:  # pragma: no cover - optional local dependency
    create_client = None  # type: ignore[assignment]

_ANALYSIS_LOCK = RLock()
_USER_LOCK = RLock()
_FEEDBACK_LOCK = RLock()
_REPORT_LOCK = RLock()

_ANALYSES: Dict[str, Dict[str, Any]] = {}
_USERS: Dict[str, Dict[str, str]] = {}
_FEEDBACK: List[Dict[str, Any]] = []
_REPORTS: List[Dict[str, Any]] = []


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_supabase_client():
    if create_client is None:
        return None
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def create_analysis(record: Dict[str, Any]) -> Dict[str, Any]:
    client = get_supabase_client()
    if client is not None:
        try:
            response = client.table("analyses").upsert(record).execute()
            data = getattr(response, "data", None) or []
            if data:
                return deepcopy(data[0])
            return deepcopy(record)
        except Exception:
            pass

    with _ANALYSIS_LOCK:
        _ANALYSES[record["analysis_id"]] = deepcopy(record)
        return deepcopy(_ANALYSES[record["analysis_id"]])


def get_analysis(analysis_id: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_client()
    if client is not None:
        try:
            response = (
                client.table("analyses")
                .select("*")
                .eq("analysis_id", analysis_id)
                .limit(1)
                .execute()
            )
            data = getattr(response, "data", None) or []
            if data:
                return deepcopy(data[0])
        except Exception:
            pass

    with _ANALYSIS_LOCK:
        analysis = _ANALYSES.get(analysis_id)
        return deepcopy(analysis) if analysis is not None else None


def list_analyses(owner: Optional[str] = None) -> List[Dict[str, Any]]:
    """List analyses; with ``owner`` set, only that user's records are returned."""
    client = get_supabase_client()
    if client is not None:
        try:
            query = client.table("analyses").select("*")
            if owner is not None:
                query = query.eq("owner", owner)
            response = query.order("created_at", desc=True).execute()
            data = getattr(response, "data", None) or []
            return list(data)
        except Exception:
            pass

    with _ANALYSIS_LOCK:
        records = (
            record
            for record in _ANALYSES.values()
            if owner is None or record.get("owner") == owner
        )
        return sorted(
            (deepcopy(record) for record in records),
            key=lambda record: record.get("created_at", ""),
            reverse=True,
        )


def delete_analysis(analysis_id: str, owner: Optional[str] = None) -> bool:
    """Delete an analysis only when an authenticated caller owns the record."""
    if owner is None:
        return False
    existing = get_analysis(analysis_id)
    if existing is None or existing.get("owner") != owner:
        return False

    client = get_supabase_client()
    if client is not None:
        try:
            client.table("analyses").delete().eq("analysis_id", analysis_id).execute()
            return True
        except Exception:
            pass

    with _ANALYSIS_LOCK:
        record = _ANALYSES.get(analysis_id)
        if record is not None and record.get("owner") == owner:
            del _ANALYSES[analysis_id]
            return True
    return False


def upsert_user(username: str, email: str, hashed_password: str) -> Dict[str, str]:
    with _USER_LOCK:
        _USERS[username] = {
            "username": username,
            "email": email,
            "hashed_password": hashed_password,
        }
        return deepcopy(_USERS[username])


def get_user(username: str) -> Optional[Dict[str, str]]:
    with _USER_LOCK:
        user = _USERS.get(username)
        return deepcopy(user) if user is not None else None


def append_feedback(username: str, message: str) -> Dict[str, Any]:
    record = {
        "username": username,
        "message": message,
        "created_at": utc_now_iso(),
    }
    with _FEEDBACK_LOCK:
        _FEEDBACK.append(record)
        return deepcopy(record)


def list_feedback() -> List[Dict[str, Any]]:
    client = get_supabase_client()
    if client is not None:
        try:
            response = client.table("feedback").select("*").order("created_at", desc=True).execute()
            data = getattr(response, "data", None) or []
            if data:
                return list(data)
        except Exception:
            pass
    with _FEEDBACK_LOCK:
        return sorted(
            (deepcopy(record) for record in _FEEDBACK),
            key=lambda record: record.get("created_at", ""),
            reverse=True,
        )


def append_report(
    username: Optional[str],
    analysis_id: Optional[str],
    reason: str,
    message: str,
) -> Dict[str, Any]:
    record = {
        "username": username or "guest",
        "analysis_id": analysis_id or "",
        "reason": reason,
        "message": message,
        "created_at": utc_now_iso(),
    }
    client = get_supabase_client()
    if client is not None:
        try:
            client.table("reports").insert(record).execute()
            return deepcopy(record)
        except Exception:
            pass
    with _REPORT_LOCK:
        _REPORTS.append(record)
        return deepcopy(record)


def list_reports() -> List[Dict[str, Any]]:
    client = get_supabase_client()
    if client is not None:
        try:
            response = client.table("reports").select("*").order("created_at", desc=True).execute()
            data = getattr(response, "data", None) or []
            if data:
                return list(data)
        except Exception:
            pass
    with _REPORT_LOCK:
        return sorted(
            (deepcopy(record) for record in _REPORTS),
            key=lambda record: record.get("created_at", ""),
            reverse=True,
        )