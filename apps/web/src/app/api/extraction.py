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


def extract_emails(text: str) -> List[str]:
    """Return unique email addresses found in ``text``."""
    if not text:
        return []
    emails = []
    for match in _EMAIL_PATTERN.findall(text):
        if match not in emails:
            emails.append(match)
    return emails