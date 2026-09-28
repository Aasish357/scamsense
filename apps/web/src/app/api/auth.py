import base64
import hashlib
import hmac
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover - optional local dependency
    Client = object  # type: ignore[assignment]
    create_client = None  # type: ignore[assignment]

from .store import get_user, upsert_user

router = APIRouter()

_PASSWORD_ITERATIONS = 120000


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
        return {"msg": "Login successful!"}

    db_user = get_user(user.username)
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"msg": "Login successful!"}
