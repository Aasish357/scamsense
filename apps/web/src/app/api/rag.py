"""Retrieval-augmented generation (RAG) over a local scam-pattern knowledge base.

Embeddings come from the local Ollama embedding model (nomic-embed-text by
default). Vectors are cached in memory after the first build so subsequent
requests only need one embedding call (the query) plus cheap cosine scoring.
"""
from __future__ import annotations

import math
import threading
from typing import Dict, List

from . import ollama_client

# Curated scam-pattern corpus used as external memory for the LLM.
KNOWLEDGE_BASE: List[Dict[str, str]] = [
    {
        "title": "Bank / payment-app impersonation phishing",
        "category": "phishing",
        "text": (
            "Scammers impersonate a bank, wallet or payment app and claim the "
            "account is suspended, locked or flagged for unauthorized activity. "
            "The message creates urgency and contains a link to a spoofed login "
            "page that harvests credentials, OTP codes or card details. Real "
            "institutions never ask customers to sign in through an email or SMS "
            "link, and genuine URLs use the official domain over HTTPS."
        ),
    },
    {
        "title": "Lottery, prize and inheritance scams",
        "category": "advance-fee",
        "text": (
            "The victim is told they won a lottery, giveaway or inheritance they "
            "never entered. To claim, they must first pay an advance fee, tax or "
            "processing charge through gift cards, crypto or a wire transfer. Any "
            "prize that requires an upfront payment is a scam, and replies to "
            "unsolicited winning notices should be ignored."
        ),
    },
    {
        "title": "Package delivery smishing (fake courier notices)",
        "category": "smishing",
        "text": (
            "An SMS or message claims a parcel cannot be delivered because of an "
            "invalid address, unpaid customs fee or failed payment. It includes a "
            "shortened or look-alike link leading to a phishing page that steals "
            "card numbers or personal data. Couriers do not collect fees via text "
            "links; track deliveries through the official courier app or website."
        ),
    },
    {
        "title": "Tech-support and fake malware alerts",
        "category": "tech-support",
        "text": (
            "A pop-up, email or call claims the device is infected with viruses or "
            "that the warranty expired, urging the victim to call a toll-free "
            "number or install remote-access software such as AnyDesk or TeamViewer. "
            "The attacker then takes control of the machine, steals passwords or "
            "demands payment. Microsoft, Apple and ISPs never make unsolicited "
            "support calls."
        ),
    },
    {
        "title": "Crypto and investment get-rich-quick schemes",
        "category": "investment-fraud",
        "text": (
            "Fraudsters promise guaranteed high returns through WhatsApp or Telegram "
            "trading groups, fake dashboards or cloned exchanges. Victims deposit "
            "funds that are shown as growing profits until they try to withdraw, at "
            "which point invented taxes or fees are demanded and the money vanishes. "
            "No legitimate investment guarantees risk-free daily profits."
        ),
    },
    {
        "title": "Romance and trust-building long cons",
        "category": "romance-scam",
        "text": (
            "The scammer builds an emotional relationship quickly on dating apps or "
            "social media, then invents a medical emergency, travel problem or "
            "investment opportunity to request money, gift cards or crypto. They "
            "avoid video calls, refuse to meet and may ask the victim to move the "
            "conversation off-platform. Never send money to someone met online who "
            "has not been met in person."
        ),
    },
    {
        "title": "Employment and task-based pay scams",
        "category": "job-scam",
        "text": (
            "Job offers arrive via WhatsApp or Telegram promising high pay for simple "
            "tasks such as liking videos, rating apps or data entry. The worker must "
            "first pay to unlock tasks, or deposits fake earnings and is asked to "
            "pay fees to withdraw. Legitimate employers never charge candidates to "
            "work or require crypto deposits to start a job."
        ),
    },
    {
        "title": "Government, tax and law-enforcement impersonation",
        "category": "impersonation",
        "text": (
            "Messages claim to come from the IRS, police, immigration or a court, "
            "alleging unpaid taxes, an arrest warrant or account freeze, and demand "
            "immediate payment via gift cards, crypto or wire. Government agencies "
            "communicate by official letter and never threaten arrest over text, "
            "email or phone."
        ),
    },
    {
        "title": "Credential harvesting via spoofed links and QR codes",
        "category": "phishing",
        "text": (
            "Phishing links use misspelled domains, unusual top-level domains such as "
            ".xyz or .top, URL shorteners, punycode or extra subdomains to imitate "
            "real brands. QR codes in emails or on flyers (quishing) hide the real "
            "destination. Before signing in, check the domain character by character "
            "and prefer typing the known official address directly."
        ),
    },
    {
        "title": "Urgency and authority manipulation tactics",
        "category": "social-engineering",
        "text": (
            "Scam messages pressure the reader with deadlines, account suspension, "
            "legal action or family emergencies and use authoritative tone to block "
            "verification. Other red flags include generic greetings, spelling "
            "errors, requests for secrecy, and payment through irreversible methods. "
            "Slow down, verify through an independent channel and never act only on "
            "an incoming message."
        ),
    },
    {
        "title": "Screenshot and message-editing forgeries",
        "category": "forgery",
        "text": (
            "Fake receipts, chat screenshots and order confirmations are generated to "
            "prove payment or identity. Inconsistencies include mismatched fonts, "
            "unaligned timestamps, impossible dates, blurry logos and improbable "
            "amounts. Verify transactions in the official banking or platform app "
            "instead of trusting an image someone sent."
        ),
    },
    {
        "title": "Deepfake audio and video voice-cloning scams",
        "category": "deepfake",
        "text": (
            "Criminals clone a relative's or executive's voice from short recordings "
            "to request urgent wire transfers or gift cards, sometimes during fake "
            "video calls. If someone you know asks for money urgently, hang up and "
            "call them back on a known number and ask a question only they could "
            "answer."
        ),
    },
]

_CACHE_LOCK = threading.Lock()
_CACHED_VECTORS: List[Dict] = []


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _document_text(document: Dict[str, str]) -> str:
    return "{}: {}".format(document["title"], document["text"])


def _ensure_index() -> List[Dict]:
    """Build (once) and return the cached embedding index for the corpus."""
    global _CACHED_VECTORS
    with _CACHE_LOCK:
        if _CACHED_VECTORS:
            return _CACHED_VECTORS
        vectors = []
        for document in KNOWLEDGE_BASE:
            vector = ollama_client.embed(_document_text(document))
            if not vector:
                # Skip documents that failed instead of poisoning the cache.
                continue
            vectors.append({"document": document, "vector": vector})
        if vectors:
            _CACHED_VECTORS = vectors
        return _CACHED_VECTORS


def reset_cache() -> None:
    """Drop cached embeddings (used by tests)."""
    global _CACHED_VECTORS
    with _CACHE_LOCK:
        _CACHED_VECTORS = []


def retrieve(query: str, top_k: int = 3) -> List[Dict]:
    """Return the knowledge-base entries most similar to ``query``.

    Each result: {title, category, text, score}. Returns [] when the embedding
    service is unavailable so callers can degrade gracefully.
    """
    if not query or not query.strip():
        return []
    try:
        index = _ensure_index()
        query_vector = ollama_client.embed(query.strip())
    except Exception:
        return []
    if not query_vector or not index:
        return []
    scored = []
    for entry in index:
        score = _cosine_similarity(query_vector, entry["vector"])
        scored.append(
            {
                "title": entry["document"]["title"],
                "category": entry["document"]["category"],
                "text": entry["document"]["text"],
                "score": round(score, 4),
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(1, top_k)]