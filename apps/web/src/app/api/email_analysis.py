"""Dedicated email analysis: message/header parsing plus authentication signals.

Fully offline. Uses the stdlib ``email`` package to read raw RFC 5322 messages
(or .eml uploads) and derives deterministic signals from the headers, MIME
structure and the body text.
"""
from __future__ import annotations

import re
from email import message_from_string
from email.utils import parseaddr
from typing import Dict, List

from .extraction import extract_links, extract_phone_numbers
from .url_analysis import BRAND_DOMAINS, _registrable_domain, analyze_url

EMAIL_BASE_SCORE = 40

DANGEROUS_ATTACHMENTS = {
    ".exe", ".scr", ".js", ".vbs", ".jar", ".bat", ".cmd", ".com", ".pif",
    ".lnk", ".iso", ".img", ".hta", ".wsf", ".msi", ".ps1", ".apk",
}
ARCHIVE_ATTACHMENTS = {".zip", ".rar", ".7z", ".gz", ".tar", ".cab"}

_AUTH_FAIL_VALUES = {"fail", "softfail", "hardfail", "permerror", "temperror"}
_ARCHIVE_PASSWORD_WORDS = ("password", "passcode", "protected", "encrypted", "unlock")


def _address(value: str) -> Dict[str, str]:
    display, address = parseaddr(value or "")
    domain = address.split("@")[-1].lower() if "@" in address else ""
    return {"display": display.strip(), "address": address.strip().lower(), "domain": domain}


def _auth_verdicts(authentication_results: str) -> Dict[str, str]:
    verdicts = {}
    lowered = (authentication_results or "").lower()
    for mechanism in ("spf", "dkim", "dmarc"):
        match = re.search(mechanism + r"=([a-z]+)", lowered)
        if match:
            verdicts[mechanism] = match.group(1)
    return verdicts


def parse_email(raw: str) -> Dict:
    """Parse a raw email into headers, body text, links and attachments."""
    message = message_from_string(raw or "")
    header_names = (
        "From", "Reply-To", "Return-Path", "Sender", "Subject", "Date",
        "Message-ID", "Authentication-Results", "Received-SPF", "X-Mailer",
    )
    headers = {}
    for name in header_names:
        value = message.get(name)
        if value:
            headers[name] = value

    body_parts: List[str] = []
    attachments: List[str] = []
    html_present = False

    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart():
                continue
            filename = part.get_filename()
            if filename:
                attachments.append(filename)
                continue
            content_type = part.get_content_type()
            if content_type == "text/html":
                html_present = True
                continue
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(payload.decode("utf-8", "ignore"))
    else:
        payload = message.get_payload(decode=True)
        if payload:
            body_parts.append(payload.decode("utf-8", "ignore"))
        elif isinstance(message.get_payload(), str):
            body_parts.append(message.get_payload())

    body = "\n".join(body_parts).strip()
    return {
        "headers": headers,
        "received_hops": len(message.get_all("Received") or []),
        "body": body,
        "html_only": html_present and not body,
        "attachments": attachments,
        "links": extract_links(body),
        "phones": extract_phone_numbers(body),
    }


def analyze_email(raw: str) -> Dict:
    """Return {signals, score_delta, parsed} for a raw email message."""
    parsed = parse_email(raw)
    headers = parsed["headers"]
    signals: List[str] = []
    delta = 0

    from_addr = _address(headers.get("From", ""))
    reply_to = _address(headers.get("Reply-To", ""))
    return_path = _address(headers.get("Return-Path", ""))

    # --- sender authentication ---------------------------------------------
    verdicts = _auth_verdicts(headers.get("Authentication-Results", ""))
    spf_header = (headers.get("Received-SPF", "") or "").lower()
    if "; spf=" in spf_header or spf_header.startswith("spf="):
        for token in re.findall(r"spf=([a-z]+)", spf_header):
            verdicts.setdefault("spf", token)

    if not headers.get("Authentication-Results"):
        signals.append("no Authentication-Results header (SPF/DKIM/DMARC unverifiable)")
        delta += 10
    for mechanism in ("spf", "dkim", "dmarc"):
        verdict = verdicts.get(mechanism)
        if verdict in _AUTH_FAIL_VALUES:
            weight = {"dmarc": 35, "spf": 25, "dkim": 20}[mechanism]
            signals.append("{} authentication failed ({})".format(mechanism.upper(), verdict))
            delta += weight

    # --- address relationships ---------------------------------------------
    if reply_to["domain"] and from_addr["domain"] and reply_to["domain"] != from_addr["domain"]:
        signals.append(
            "Reply-To ({}) differs from the From domain ({})".format(
                reply_to["domain"], from_addr["domain"]
            )
        )
        delta += 20
    if return_path["domain"] and from_addr["domain"] and return_path["domain"] != from_addr["domain"]:
        signals.append(
            "Return-Path ({}) differs from the From domain ({})".format(
                return_path["domain"], from_addr["domain"]
            )
        )
        delta += 15

    # --- display-name brand spoofing and lookalike sender domains ----------
    display_lower = from_addr["display"].lower()
    registrable = _registrable_domain(from_addr["domain"])
    for brand, official in BRAND_DOMAINS.items():
        if brand in display_lower and registrable not in official:
            signals.append(
                "display name claims '{}' but the sender domain is {}".format(
                    brand, from_addr["domain"] or "missing"
                )
            )
            delta += 40
            break

    if from_addr["domain"]:
        # Scanned as https:// because sender domains carry no scheme; a bare
        # "no HTTPS" note would flag every legitimate sender.
        sender_scan = analyze_url("https://" + from_addr["domain"])
        sender_signals = [
            signal for signal in sender_scan["signals"]
            if "non-HTTPS" not in signal and "credential-themed path" not in signal
        ]
        if sender_signals:
            signals.append(
                "sender domain {}: {}".format(from_addr["domain"], "; ".join(sender_signals))
            )
            delta += min(35, sender_scan["score_delta"])

    # --- attachments --------------------------------------------------------
    for name in parsed["attachments"]:
        lowered = name.lower()
        suffix = lowered[lowered.rfind("."):] if "." in lowered else ""
        if suffix in DANGEROUS_ATTACHMENTS:
            signals.append("dangerous attachment ({})".format(name))
            delta += 40
        elif suffix in ARCHIVE_ATTACHMENTS:
            body_lower = (parsed["body"] + " " + headers.get("Subject", "")).lower()
            if any(word in body_lower for word in _ARCHIVE_PASSWORD_WORDS):
                signals.append("password-protected archive attachment ({})".format(name))
                delta += 25
            else:
                signals.append("archive attachment ({})".format(name))
                delta += 10

    # --- message structure --------------------------------------------------
    if not headers.get("Message-ID"):
        signals.append("missing Message-ID header")
        delta += 10
    if parsed["received_hops"] == 0:
        signals.append("no Received headers (delivery path unverifiable)")
        delta += 10
    elif parsed["received_hops"] > 6:
        signals.append("unusually long delivery path ({} hops)".format(parsed["received_hops"]))
        delta += 10
    if parsed["html_only"]:
        signals.append("HTML-only body with no plain-text alternative")
        delta += 10

    weak_findings = delta < 20
    return {
        "parsed": parsed,
        "signals": signals,
        "score_delta": min(95, delta),
        # Weak header findings alone (missing Message-ID, no Received chain in a
        # pasted message) must not push a clean email into "caution" territory.
        "suggested_score": 0 if weak_findings else min(95, EMAIL_BASE_SCORE + delta),
    }