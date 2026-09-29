"""Repair the links that OCR mangles in screenshot text.

Tesseract routinely breaks a URL apart: spaces instead of slashes, a missing
colon, and dots replaced by spaces. The result is text that still *contains* a
malicious link but that no URL parser will recognise, so the risk engine sees
nothing and a phishing screenshot can score as harmless.

This module reconstructs those links from the OCR text so the deterministic URL
analyzer gets a well-formed URL. It only ever rewrites a region that already
starts with "http", and it returns what it recovered so the caller can disclose
it.
"""
from __future__ import annotations

import re
from typing import List, Tuple

# "h t t p" with spaces is the most common OCR break; allow it explicitly.
_SCHEME = re.compile(r"h\s*t\s*t\s*p(?:\s*s)?\s*[:;.]?\s*[/|\\](?:\s*[/|\\])?\s*", re.IGNORECASE)
# Single characters count: a label like "192.0.2.44" has one-digit parts.
_TOKEN = re.compile(r"[A-Za-z0-9\-_]+")
_MAX_HOST_TOKENS = 6
_MAX_REGION_CHARS = 120
# A trailing token that looks like a real TLD ends the host.
_TLD_LIKE = re.compile(r"^[A-Za-z]{2,24}$")
_IPV4 = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def _looks_like_tld(token: str) -> bool:
    return bool(_TLD_LIKE.match(token)) and "." not in token


def _build_host(region: str) -> Tuple[str, str]:
    """Return (host, remainder) for a run of OCR'd host tokens."""
    tokens = _TOKEN.findall(region)[:_MAX_HOST_TOKENS]
    if not tokens:
        return "", ""

    host = tokens[0]
    consumed = region.find(tokens[0]) + len(tokens[0])
    for token in tokens[1:]:
        # A TLD-looking token ends the host: paypal-verify-accout. example -> ...example
        # A negative start would make str.find search from the end of the
        # string, silently pointing at the wrong token.
        position = region.find(token, max(0, consumed - len(token)))
        host = "{}.{}".format(host, token)
        consumed = (position if position >= 0 else consumed) + len(token)
        if _IPV4.match(host):
            return host, region[consumed:].lstrip(" .")
        if _looks_like_tld(token):
            return host, region[consumed:].lstrip(" .")
    return host, region[consumed:].lstrip(" .")


def repair_urls(text: str) -> Tuple[str, List[str]]:
    """Return (text with recovered links rewritten, list of recovered URLs)."""
    # OCR can insert spaces between the letters ("h t t p"), so the cheap
    # pre-check has to allow that form too.
    if not text or not re.search(r"h\s*t\s*t\s*p", text, re.IGNORECASE):
        return text or "", []

    recovered: List[str] = []
    out_lines: List[str] = []

    for line in text.splitlines():
        match = _SCHEME.search(line)
        if not match:
            out_lines.append(line)
            continue

        prefix = line[: match.start()]
        region = line[match.end(): match.end() + _MAX_REGION_CHARS]
        from .extraction import extract_links

        if extract_links(line):
            # The line already contains a well-formed link, so OCR did not damage
            # it. Rewriting it would only risk corrupting a URL that works.
            out_lines.append(line)
            continue

        host, remainder = _build_host(region)
        if not host:
            out_lines.append(line)
            continue

        path = remainder.split()[0].strip("/") if remainder else ""
        url = "http://{}/{}".format(host, path) if path else "http://{}".format(host)
        url = re.sub(r"[^\x21-\x7e]", "", url)
        recovered.append(url)
        out_lines.append("{}{}".format(prefix, url))

    return "\n".join(out_lines), recovered