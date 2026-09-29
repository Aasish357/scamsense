"""A small, dependency-free rate limiter for the public analysis endpoints.

ScamSense is meant to be reachable by anyone, which means an unauthenticated
`POST /analyze` can be called by anyone. This is a first line of defence, not a
security boundary: the buckets live in process memory, so they reset on restart
and are per instance. Put a real limiter at the edge (CDN, platform rate limit)
in front of a public deployment as well.

The limits are read on every call rather than at import time so tests (and an
operator) can tune them without a code change.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Deque, Dict

from fastapi import HTTPException, Request

DEFAULT_WINDOW_SECONDS = 60.0
DEFAULT_MAX_REQUESTS = 120

_BUCKETS: Dict[str, Deque[float]] = {}
_LOCK = threading.Lock()
_MAX_TRACKED_CLIENTS = 5000


def window_seconds() -> float:
    try:
        return float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS))
    except ValueError:
        return DEFAULT_WINDOW_SECONDS


def max_requests() -> int:
    try:
        return int(os.getenv("RATE_LIMIT_MAX_REQUESTS", DEFAULT_MAX_REQUESTS))
    except ValueError:
        return DEFAULT_MAX_REQUESTS


def client_key(request: Request) -> str:
    """Identify the caller, honouring the proxy header platforms set."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()
    client = request.client
    return client.host if client and client.host else "unknown"


def reset() -> None:
    """Drop all buckets (used by tests)."""
    with _LOCK:
        _BUCKETS.clear()


def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency: raise 429 once a client exceeds the window budget."""
    now = time.time()
    key = client_key(request)
    window = window_seconds()
    limit = max_requests()

    with _LOCK:
        bucket = _BUCKETS.setdefault(key, deque())
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window - (now - bucket[0])) + 1)
            raise HTTPException(
                status_code=429,
                detail="Too many analyses from this address. Try again in {} seconds.".format(
                    retry_after
                ),
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)

        if len(_BUCKETS) > _MAX_TRACKED_CLIENTS:
            for stale_key in [
                candidate
                for candidate, stamps in _BUCKETS.items()
                if not stamps or now - stamps[-1] > window
            ]:
                _BUCKETS.pop(stale_key, None)