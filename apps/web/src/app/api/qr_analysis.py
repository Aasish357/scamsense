"""QR code analysis for uploaded images.

Decodes QR payloads locally with OpenCV (no network, no upload to third
parties) and scores the decoded content with the same lexical URL engine used
for text analysis. Payment-app QR payloads (upi:, bitcoin:, etc.) are flagged
explicitly because they are a common "scan to pay" scam vector.
"""
from __future__ import annotations

from typing import Dict, List

from .url_analysis import analyze_url

QR_BASE_SCORE = 40

_PAYMENT_SCHEMES = ("upi:", "bitcoin:", "ethereum:", "bitpay:", "litecoin:", "paytmmp:", "phonepe:")


def decode_qr_payloads(image_bytes: bytes) -> List[str]:
    """Return the QR payloads found in an image (empty list when unsupported)."""
    if not image_bytes:
        return []
    try:
        import cv2
        import numpy as np
    except ImportError:  # pragma: no cover - optional local dependency
        return []

    try:
        buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            return []
        detector = cv2.QRCodeDetector()
        candidates = [image]

        # Small or tightly-cropped codes need a quiet zone and upscaling before
        # OpenCV's detector can lock onto the finder patterns.
        height, width = image.shape[:2]
        short_side = max(1, min(height, width))
        if short_side < 300:
            scale = max(2, int(600 / short_side))
            candidates.append(
                cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
            )
        candidates.append(
            cv2.copyMakeBorder(
                candidates[-1], 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(255, 255, 255)
            )
        )

        for candidate in candidates:
            payloads = _decode_variant(detector, candidate)
            if payloads:
                return payloads
        return []
    except Exception:
        return []


def _decode_variant(detector, image) -> List[str]:
    try:
        ok, decoded, _points, _straight = detector.detectAndDecodeMulti(image)
        if ok and decoded is not None:
            payloads = [payload.strip() for payload in decoded if payload and payload.strip()]
            if payloads:
                return payloads
    except Exception:
        pass
    try:
        value, _points, _straight = detector.detectAndDecode(image)
        if value and value.strip():
            return [value.strip()]
    except Exception:
        return []
    return []


def analyze_qr(image_bytes: bytes) -> Dict:
    """Decode QR payloads and score them; returns content, signals and score."""
    payloads = decode_qr_payloads(image_bytes)
    signals: List[str] = []
    delta = 0

    for payload in payloads:
        lowered = payload.lower()
        if lowered.startswith(_PAYMENT_SCHEMES):
            signals.append(
                "payment QR payload ({}): {}".format(lowered.split(":", 1)[0], payload[:80])
            )
            delta += 35
            continue
        if lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("www."):
            scan = analyze_url(payload)
            if scan["signals"]:
                signals.append(
                    "QR link {}: {}".format(payload, "; ".join(scan["signals"]))
                )
                delta += scan["score_delta"]
            else:
                signals.append("QR link decodes to {}".format(payload))
            continue
        if lowered.startswith("mailto:"):
            signals.append("QR payload opens an email compose window ({})".format(payload[:60]))
            delta += 10
            continue
        if lowered.startswith("tel:"):
            signals.append("QR payload dials a phone number ({})".format(payload[:60]))
            delta += 10
            continue
        signals.append("QR payload is plain text: {}".format(payload[:120]))

    delta = min(95, delta)
    return {
        "payloads": payloads,
        "signals": signals,
        "score_delta": delta,
        "content": "\n".join(payloads),
        "suggested_score": min(95, QR_BASE_SCORE + delta) if (delta and payloads) else 0,
    }