"""Text-level signals that are neither a URL nor a phone number.

Payment URIs (``upi://pay?...``, ``bitcoin:<address>``) and click-to-dial
``tel:`` links show up in plain SMS and email bodies, where the phone extractor
never sees a dialable number and the URL analyzer never sees a host. Both are
common scam lures in exactly that form, so they get their own small detector.

The evaluation harness surfaced this gap: a message containing a UPI payment
request was invisible to every other detector.
"""
from __future__ import annotations

import re
from typing import Dict, List

# A bare "bitcoin:" in prose is rare, but "pay upi:" is not - so a scheme only
# counts when it is followed by something that actually looks like a payment
# request or an address.
_PAYMENT_URI_PATTERN = re.compile(
    r"\b(upi|bitcoin|bitcoincash|ethereum|litecoin|monero|dogecoin|tezos):(//)?[^\s]*",
    re.IGNORECASE,
)
_TEL_URI_PATTERN = re.compile(r"\btel:\+?[0-9][0-9\s().-]{5,}", re.IGNORECASE)

BASE_TEXT_SCORE = 30
MIN_CRYPTO_ADDRESS_CHARS = 20


def _payment_hits(text: str) -> List[str]:
    hits: List[str] = []
    for match in _PAYMENT_URI_PATTERN.finditer(text or ""):
        scheme = match.group(1).lower()
        remainder = match.group(0)[len(scheme) + 1:]
        if scheme == "upi":
            if "pa=" not in remainder.lower():
                continue
        elif len(re.sub(r"[^A-Za-z0-9]", "", remainder)) < MIN_CRYPTO_ADDRESS_CHARS:
            continue
        hits.append(match.group(0)[:80])
    return hits


def analyze_text_signals(text: str) -> Dict:
    """Return {signals, score_delta} for payment and dial URIs in plain text."""
    signals: List[str] = []
    delta = 0

    payments = _payment_hits(text)
    if payments:
        signals.append(
            "payment URI in the message text ({}): {}".format(
                len(payments), payments[0]
            )
        )
        delta += 40

    if _TEL_URI_PATTERN.search(text or ""):
        # Informational only, matching how the QR analyzer treats tel: payloads:
        # a dial link is not evidence on its own, and the pressure signals
        # ("call now", urgency + number) are covered by the phone detectors.
        signals.append("click-to-dial tel: link in the message text")
        delta += 5

    return {"signals": signals, "score_delta": min(95, delta)}