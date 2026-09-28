"""Authentication: account creation, login, and signed bearer tokens.

Tokens are stateless HMAC-SHA256 signed payloads built with the standard
library only, so the API gains no new dependencies. Configure AUTH_SECRET in
production; a random per-process secret is the fallback (sessions then reset
on restart, acceptable for local/dev use).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover - optional local dependency
    Client = object  # type: ignore[assignment]
    create_client = None  # type: ignore[assignment]

from .store import get_user, upsert_user

router = APIRouter()

_PASSWORD_ITERATIONS = 120000
_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
_FALLBACK_SECRET = uuid.uuid4().bytes


class User(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


def get_supabase() -> Optional[Client]:
    if create_client is None:
        return None
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def get_password_hash(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PASSWORD_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        _PASSWORD_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(derived).decode("ascii"),
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        algorithm, iterations, salt_b64, derived_b64 = hashed_password.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(derived_b64.encode("ascii"))
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            int(iterations),
        )
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def _secret() -> bytes:
    configured = os.getenv("AUTH_SECRET", "").strip()
    if configured:
        return configured.encode("utf-8")
    return _FALLBACK_SECRET


def create_token(username: str) -> str:
    """Issue a signed token: base64url(payload).hex(hmac_sha256(payload))."""
    payload = {"sub": username, "exp": int(time.time()) + _TOKEN_TTL_SECONDS}
    raw = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    signature = hmac.new(_secret(), raw.encode("ascii"), hashlib.sha256).hexdigest()
    return "{}.{}".format(raw, signature)


def parse_token(token: str) -> Optional[str]:
    """Return the username for a valid, unexpired token; otherwise None."""
    try:
        raw, signature = token.split(".", 1)
        expected = hmac.new(_secret(), raw.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8"))
        if int(payload.get("exp", 0)) < time.time():
            return None
        subject = payload.get("sub")
        return subject if isinstance(subject, str) and subject else None
    except Exception:
        return None


def get_optional_user(request: Request) -> Optional[str]:
    """FastAPI dependency: username from ``Authorization: Bearer`` if present."""
    header = request.headers.get("Authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    return parse_token(token) if token else None


def require_user(request: Request) -> str:
    """FastAPI dependency: 401 unless a valid token identifies a user."""
    user = get_optional_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return user


@router.post("/register")
async def register_user(user: User):
    supabase = get_supabase()
    if supabase is not None:
        existing_user = supabase.table("users").select("*").eq("username", user.username).execute()
        if existing_user.data:
            raise HTTPException(status_code=400, detail="Username already registered.")

        supabase.table("users").insert(
            {
                "username": user.username,
                "email": user.email,
                "hashed_password": get_password_hash(user.password),
            }
        ).execute()
        return {"msg": "User registered successfully!"}

    existing_user = get_user(user.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered.")

    upsert_user(user.username, user.email, get_password_hash(user.password))
    return {"msg": "User registered successfully!"}


@router.post("/login")
async def login_user(user: LoginRequest):
    supabase = get_supabase()
    if supabase is not None:
        db_user = supabase.table("users").select("*").eq("username", user.username).execute()
        if not db_user.data or not verify_password(user.password, db_user.data[0]["hashed_password"]):
            raise HTTPException(status_code=400, detail="Incorrect username or password")
        return {"msg": "Login successful!", "token": create_token(user.username), "username": user.username}

    db_user = get_user(user.username)
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"msg": "Login successful!", "token": create_token(user.username), "username": user.username}