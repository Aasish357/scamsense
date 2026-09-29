"""Passive lexical URL analysis (no active fetching).

Purely local, deterministic inspection of URL strings: structure, host
anomalies, homoglyph/punycode tricks, suspicious TLDs, known shorteners and
brand-lookalike domains. Used by the heuristic scorer and surfaced to the LLM
as evidence. Never performs network requests.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import urlsplit

SUSPICIOUS_TLDS = {
    "xyz", "top", "zip", "mov", "rest", "loan", "work", "click", "link",
    "country", "gq", "tk", "ml", "cf", "ga", "pw", "cc", "icu", "monster",
    "live", "beauty", "hair", "quest", "rest", "cfd", "sbs", "bond",
}

SHORTENER_DOMAINS = {
    "bit.ly", "t.co", "tinyurl.com", "goo.gl", "is.gd", "ow.ly", "cutt.ly",
    "rebrand.ly", "buff.ly", "rb.gy", "shorturl.at", "tiny.cc", "lnkd.in",
    "amzn.to", "youtu.be", "wp.me", "trib.al", "ift.tt",
}

# Commonly impersonated brands and their genuine eTLD+1 domains.
BRAND_DOMAINS = {
    "paypal": {"paypal.com", "paypal.me"},
    "apple": {"apple.com", "icloud.com"},
    "microsoft": {"microsoft.com", "live.com", "outlook.com"},
    "google": {"google.com", "gmail.com"},
    "amazon": {"amazon.com", "amazon.in"},
    "netflix": {"netflix.com"},
    "instagram": {"instagram.com"},
    "facebook": {"facebook.com", "fb.com"},
    "whatsapp": {"whatsapp.com", "wa.me"},
    "binance": {"binance.com"},
    "coinbase": {"coinbase.com"},
}

# Cyrillic/Greek characters frequently used to spoof Latin hostnames.
HOMOGLYPH_MAP = {
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c",
    "\u0443": "y", "\u0445": "x", "\u0456": "i", "\u0455": "s", "\u0434": "d",
    "\u03b1": "a", "\u03b5": "e", "\u03bf": "o", "\u03c1": "p", "\u03c4": "t",
    "\u03c5": "u", "\u03bd": "v", "\u03ba": "k", "\u03b9": "i", "\u03c3": "s",
}

_LEET_MAP = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t"})
# "1" is also commonly swapped for "l" (paypa1 -> paypal), which the map above
# cannot express, so a second substitution is checked before giving up.
_LEET_MAP_ALT = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t"})

_SENSITIVE_PATH_WORDS = (
    "login", "signin", "sign-in", "verify", "verification", "secure", "account",
    "update", "confirm", "password", "reset", "recover", "restore", "unlock",
    "suspend", "billing", "wallet", "otp", "claim", "authorize", "signin",
)

BASE_URL_SCORE = 40


def _normalize_host(host: str) -> str:
    """Lower-case, strip ports/brackets and map homoglyphs to Latin."""
    host = (host or "").strip().lower().rstrip(".")
    if host.startswith("["):
        host = host.strip("[]")
    return "".join(HOMOGLYPH_MAP.get(ch, ch) for ch in host)


def _registrable_domain(host: str) -> str:
    """Best-effort eTLD+1 without a public-suffix list (last two labels)."""
    parts = [part for part in host.split(".") if part]
    if len(parts) <= 2:
        return host
    return ".".join(parts[-2:])


def _is_ip_host(host: str) -> bool:
    bare = host.strip("[]")
    if bare.count(".") == 3:
        return all(segment.isdigit() and int(segment) <= 255 for segment in bare.split("."))
    return ":" in bare


def analyze_url(url: str) -> Dict:
    """Return {url, signals, score_delta} for one URL string.

    ``signals`` is a list of human-readable labels; ``score_delta`` is the
    deterministic risk contribution of this URL (0 if it looks clean).
    """
    signals: List[str] = []
    raw = (url or "").strip()
    if not raw:
        return {"url": url, "signals": [], "score_delta": 0}

    try:
        parts = urlsplit(raw if "://" in raw else "http://" + raw)
    except ValueError:
        return {"url": raw, "signals": ["unparseable URL"], "score_delta": BASE_URL_SCORE + 30}

    host_raw = (parts.hostname or "").lower()
    host = _normalize_host(host_raw)
    registrable = _registrable_domain(host)

    delta = 0

    # --- scheme / structure -------------------------------------------------
    if parts.scheme == "http":
        signals.append("non-HTTPS link")
        delta += 5
    if parts.username or parts.password:
        signals.append("credentials embedded in URL")
        delta += 30
    if "@" in raw.split("://", 1)[-1].split("/", 1)[0]:
        signals.append("@-sign in host (destination masking)")
        delta += 30
    if _is_ip_host(host_raw):
        signals.append("raw IP address instead of a domain")
        delta += 30

    # --- host anomalies -----------------------------------------------------
    if "xn--" in host:
        signals.append("punycode (IDN) hostname")
        delta += 35
    if any(ord(ch) > 127 for ch in host_raw):
        signals.append("non-ASCII characters in hostname (homoglyph risk)")
        delta += 35
    if host.count(".") >= 5:
        signals.append("unusually many subdomains")
        delta += 10
    if host.count("-") >= 2:
        signals.append("multiple hyphens in domain")
        delta += 10
    if len(host) >= 30:
        signals.append("very long hostname")
        delta += 10
    if len(raw) >= 120:
        signals.append("very long URL")
        delta += 5

    # --- TLD / shortener ----------------------------------------------------
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld in SUSPICIOUS_TLDS:
        signals.append("suspicious TLD (.{})".format(tld))
        delta += 25
    if registrable in SHORTENER_DOMAINS or host in SHORTENER_DOMAINS:
        signals.append("URL shortener hides the real destination")
        delta += 15

    # --- brand lookalikes ---------------------------------------------------
    labels = [label for label in host.split(".") if label]
    for brand, official in BRAND_DOMAINS.items():
        if registrable in official or host in official:
            continue
        leet_host = host.translate(_LEET_MAP)
        leet_host_alt = host.translate(_LEET_MAP_ALT)
        if brand in leet_host or brand in leet_host_alt:
            if brand in host:
                signals.append("brand '{}' referenced from a non-official domain".format(brand))
                delta += 40
            else:
                signals.append("look-alike spelling of '{}' (digits swapped)".format(brand))
                delta += 35
            continue
        # Typosquat stems (paypa1.com, googIe.com) must stay label-sized so
        # everyday words like "apply-now.com" are not mistaken for Apple.
        stem = brand[:-1] if len(brand) > 5 else brand
        if len(stem) < 5:
            continue
        for label in labels:
            if stem in label and abs(len(label) - len(brand)) <= 2:
                signals.append("possible look-alike of '{}' brand".format(brand))
                delta += 35
                break

    # --- path wording -------------------------------------------------------
    path_words = (parts.path or "").lower()
    hit_words = [word for word in _SENSITIVE_PATH_WORDS if word in path_words]
    if hit_words:
        signals.append("credential-themed path ({})".format(", ".join(sorted(set(hit_words))[:4])))
        # Weak on its own: plenty of legitimate pages use /login or /reset, so
        # this informs the score without pushing a first-party link into
        # "suspicious" territory by itself.
        delta += 5

    delta = min(95, delta)
    return {"url": raw, "signals": signals, "score_delta": delta}


def analyze_urls(urls: List[str]) -> Dict:
    """Analyze several URLs; returns per-URL results and the aggregate delta."""
    results = [analyze_url(url) for url in urls if url]
    total = 0
    for result in results:
        # One message only needs the single worst URL to hit the ceiling.
        total = max(total, result["score_delta"])
    return {"results": results, "score_delta": total}