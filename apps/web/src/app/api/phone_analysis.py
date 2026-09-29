"""Phone-number risk signals for submitted messages.

Deterministic, offline checks over the numbers found in a message plus the
surrounding wording. No lookups, no third-party services.
"""
from __future__ import annotations

import re
from typing import Dict, List

from .extraction import extract_phone_numbers, normalize_phone

PHONE_BASE_SCORE = 40

# Country codes of the real organisations most often impersonated.
BRAND_PHONE_COUNTRY = {
    "paypal": "1",
    "apple": "1",
    "microsoft": "1",
    "google": "1",
    "amazon": "1",
    "netflix": "1",
    "facebook": "1",
    "instagram": "1",
    "whatsapp": "1",
    "binance": "1",
    "coinbase": "1",
    "irs": "1",
}

_MESSAGING_APPS = (
    "whatsapp", "telegram", "signal", "wechat", "hike", "skype", "hangouts",
)

_URGENCY_WORDS = (
    "urgent", "immediately", "right away", "within 24", "suspend", "blocked",
    "refund", "verify", "kyc", "tax", "police", "court", "lottery", "prize",
    "legal action", "arrest",
)

_CALL_WORDS = ("call", "dial", "phone us", "contact us on", "helpline", "toll-free", "toll free")


def _has_repeated_or_sequential_pattern(digits: str) -> str:
    if len(set(digits)) == 1 and len(digits) >= 8:
        return "every digit identical"
    for index in range(len(digits) - 5):
        window = digits[index:index + 6]
        if all(int(window[i + 1]) - int(window[i]) == 1 for i in range(len(window) - 1)):
            return "sequential digits"
        if all(int(window[i]) - int(window[i + 1]) == 1 for i in range(len(window) - 1)):
            return "sequential digits"
    for digit in set(digits):
        if digits.count(digit) >= max(6, len(digits) - 2):
            return "one digit repeated throughout"
    return ""


def _country_code(number: str) -> str:
    """Best-effort calling-code extraction; only used for brand mismatch checks."""
    if not number.startswith("+"):
        return ""
    digits = number[1:]
    if digits.startswith("1"):
        return "1"
    return digits[:2] if digits else ""


def _premium_rate(number: str) -> bool:
    digits = number.lstrip("+")
    # US/Canada 1-900, UK 09xx, Germany 0900 and Australia 190x premium services.
    premium_prefixes = ("1900", "900", "449", "49900", "6119")
    return any(digits.startswith(prefix) for prefix in premium_prefixes)


def analyze_phone_number(number: str, context: str) -> Dict:
    """Return {number, signals, score_delta} for one phone number."""
    signals: List[str] = []
    delta = 0
    normalized = normalize_phone(number)
    digits = normalized.lstrip("+")
    lowered = (context or "").lower()

    if _premium_rate(normalized):
        signals.append("premium-rate number (high per-minute charge)")
        delta += 35

    pattern = _has_repeated_or_sequential_pattern(digits)
    if pattern:
        signals.append("number uses a {} pattern".format(pattern))
        delta += 20

    country = _country_code(normalized)
    if country:
        for brand, brand_country in BRAND_PHONE_COUNTRY.items():
            if brand in lowered and country != brand_country:
                signals.append(
                    "claims to be '{}' but shares a +{} contact number".format(brand, country)
                )
                delta += 25
                break

    if any(app in lowered for app in _MESSAGING_APPS):
        signals.append("contact routed through a messaging app rather than official support")
        delta += 15

    urgency_hit = any(word in lowered for word in _URGENCY_WORDS)
    call_hit = any(word in lowered for word in _CALL_WORDS)
    if urgency_hit and call_hit:
        signals.append("urgency combined with a request to call the number")
        delta += 20
    elif call_hit and not country and len(digits) >= 10:
        signals.append("national-format callback number in an unsolicited message")
        delta += 10

    if "tel:" in lowered:
        signals.append("click-to-dial link")
        delta += 5

    return {
        "number": number,
        "normalized": normalized,
        "signals": signals,
        "score_delta": min(60, delta),
    }


def analyze_phones(text: str) -> Dict:
    """Analyze every phone number in a message and aggregate the worst signals."""
    numbers = extract_phone_numbers(text or "")
    results = [analyze_phone_number(number, text or "") for number in numbers]
    delta = 0
    for result in results:
        delta = max(delta, result["score_delta"])
    if len(numbers) >= 3:
        delta = min(60, delta + 5)
        results.append(
            {
                "number": "(multiple)",
                "normalized": "",
                "signals": ["{} different contact numbers in one message".format(len(numbers))],
                "score_delta": 0,
            }
        )
    return {"numbers": numbers, "results": results, "score_delta": delta}