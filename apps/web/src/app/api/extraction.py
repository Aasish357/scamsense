"""Shared text-extraction helpers (links and emails) used by analysis endpoints."""
from __future__ import annotations

import re
from typing import List

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def _clean(token: str) -> str:
    return token.rstrip(".,;:!?)]}\"")


def extract_links(text: str) -> List[str]:
    """Return unique web links found in text, preserving appearance order."""
    if not text:
        return []
    links = []
    for match in _URL_PATTERN.findall(text):
        cleaned = _clean(match)
        if cleaned and cleaned not in links:
            links.append(cleaned)
    return links


_PHONE_PATTERN = re.compile(
    r"(?:(?<=\s)|^)(?:\+\d{1,3}[\s.\-]?)?(?:\(\d{1,4}\)[\s.\-]?)?(?:\d[\s.\-]?){7,14}\d(?=\s|$|[.,;:!?)\]])"
)
_NON_DIGIT = re.compile(r"\D+")


def normalize_phone(value: str) -> str:
    """Strip formatting from a phone number, keeping a leading '+'-country code digits."""
    cleaned = _NON_DIGIT.sub("", value or "")
    if value and value.strip().startswith("+"):
        return "+" + cleaned
    return cleaned


def extract_phone_numbers(text: str) -> List[str]:
    """Return unique phone numbers found in text, normalized and de-duplicated."""
    if not text:
        return []
    found = []
    for match in _PHONE_PATTERN.findall(text):
        digits = _NON_DIGIT.sub("", match)
        # Reject prices, years and short codes; keep plausible phone lengths.
        if len(digits) < 8 or len(digits) > 15:
            continue
        normalized = normalize_phone(match)
        if normalized not in found:
            found.append(normalized)
    return found


def extract_emails(text: str) -> List[str]:
    """Return unique email addresses found in ``text``."""
    if not text:
        return []
    emails = []
    for match in _EMAIL_PATTERN.findall(text):
        if match not in emails:
            emails.append(match)
    return emails