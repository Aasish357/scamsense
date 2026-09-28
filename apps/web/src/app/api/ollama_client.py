"""Thin HTTP client for a local Ollama server.

Uses only the Python standard library so the backend keeps working even when
optional third-party dependencies are not installed. All network calls are
blocking; endpoints that use this module are declared as sync ``def`` so
FastAPI runs them in its worker thread pool and the event loop stays free to
serve other requests concurrently.

Configuration (environment variables):
    OLLAMA_HOST            default http://127.0.0.1:11434
    OLLAMA_MODEL           chat/analysis model, default phi3:mini
    OLLAMA_VISION_MODEL    image understanding model, default moondream
    OLLAMA_EMBED_MODEL     embedding model, default nomic-embed-text:latest
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_HOST = "http://127.0.0.1:11434"


def host() -> str:
    return os.getenv("OLLAMA_HOST", DEFAULT_HOST).strip().rstrip("/")


def chat_model() -> str:
    return os.getenv("OLLAMA_MODEL", "phi3:mini").strip()


def vision_model() -> str:
    return os.getenv("OLLAMA_VISION_MODEL", "moondream").strip()


def embed_model() -> str:
    return os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest").strip()


def _post(path: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "{}{}".format(host(), path),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def is_available(timeout: float = 1.5) -> bool:
    """Return True when the Ollama server answers on the configured host."""
    try:
        request = urllib.request.Request("{}/api/tags".format(host()))
        with urllib.request.urlopen(request, timeout=timeout):
            return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def list_models(timeout: float = 3.0) -> list:
    """Return the names of the models pulled into the local Ollama registry."""
    try:
        request = urllib.request.Request("{}/api/tags".format(host()))
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return [entry.get("name", "") for entry in data.get("models", [])]
    except (urllib.error.URLError, OSError, ValueError):
        return []


def generate(
    prompt: str,
    model: str = None,
    images: list = None,
    json_format: bool = False,
    timeout: float = 120.0,
    options: dict = None,
) -> str:
    """Run a single non-streaming completion and return the raw text."""
    payload = {
        "model": model or chat_model(),
        "prompt": prompt,
        "stream": False,
    }
    if images:
        payload["images"] = images
    if json_format:
        payload["format"] = "json"
    if options:
        payload["options"] = options
    data = _post("/api/generate", payload, timeout)
    return (data.get("response") or "").strip()


def embed(text: str, model: str = None, timeout: float = 30.0) -> list:
    """Return the embedding vector for a single text using Ollama."""
    payload = {
        "model": model or embed_model(),
        "prompt": text,
    }
    data = _post("/api/embeddings", payload, timeout)
    vector = data.get("embedding") or []
    return [float(value) for value in vector]