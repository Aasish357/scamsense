"""Stable machine-readable codes for every deterministic signal.

The analyzers emit human-readable signal strings ("suspicious TLD (.top)"). The
evaluation harness needs stable identifiers so it can measure each detector
separately, and so results stay comparable across runs when wording changes.

This registry is the single place that maps one to the other. The analyzers
themselves are untouched, and ``tests/unit/test_evaluation.py`` fails if any
signal a corpus sample produces is missing here - so a newly added signal can
never silently go unmeasured.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

# (code, family, pattern) - ordered from most specific to most general.
REGISTRY: Tuple[Tuple[str, str, str], ...] = (
    # --- URL ----------------------------------------------------------------
    ("url.no_https", "url", r"^non-HTTPS link$"),
    ("url.embedded_credentials", "url", r"^credentials embedded in URL$"),
    ("url.at_masking", "url", r"^@-sign in host"),
    ("url.ip_host", "url", r"^raw IP address instead of a domain$"),
    ("url.punycode", "url", r"^punycode \(IDN\) hostname$"),
    ("url.non_ascii_host", "url", r"^non-ASCII characters in hostname"),
    ("url.many_subdomains", "url", r"^unusually many subdomains$"),
    ("url.multiple_hyphens", "url", r"^multiple hyphens in domain$"),
    ("url.long_hostname", "url", r"^very long hostname$"),
    ("url.long_url", "url", r"^very long URL$"),
    ("url.suspicious_tld", "url", r"^suspicious TLD \(\."),
    ("url.shortener", "url", r"^URL shortener hides the real destination$"),
    ("url.brand_foreign_domain", "url", r"^brand '.+' referenced from a non-official domain$"),
    ("url.brand_leet", "url", r"^look-alike spelling of '.+' \(digits swapped\)$"),
    ("url.brand_typosquat", "url", r"^possible look-alike of '.+' brand$"),
    ("url.credential_path", "url", r"^credential-themed path \("),
    # --- phone --------------------------------------------------------------
    ("phone.premium_rate", "phone", r"^premium-rate number"),
    ("phone.digit_pattern", "phone", r"^number uses a .+ pattern$"),
    ("phone.brand_country_mismatch", "phone", r"^claims to be '.+' but shares a \+\d+ contact number$"),
    ("phone.messaging_app", "phone", r"^contact routed through a messaging app"),
    ("phone.urgency_callback", "phone", r"^urgency combined with a request to call"),
    ("phone.national_callback", "phone", r"^national-format callback number"),
    ("phone.tel_link", "phone", r"^click-to-dial link$"),
    ("phone.multiple_numbers", "phone", r"^\d+ different contact numbers"),
    # --- email --------------------------------------------------------------
    ("email.no_auth_results", "email", r"^no Authentication-Results header"),
    ("email.spf_fail", "email", r"^SPF authentication failed"),
    ("email.dkim_fail", "email", r"^DKIM authentication failed"),
    ("email.dmarc_fail", "email", r"^DMARC authentication failed"),
    ("email.reply_to_mismatch", "email", r"^Reply-To \(.*\) differs from the From domain"),
    ("email.return_path_mismatch", "email", r"^Return-Path \(.*\) differs from the From domain"),
    ("email.display_name_spoof", "email", r"^display name claims '.+' but the sender domain is"),
    ("email.sender_domain_risk", "email", r"^sender domain .+: "),
    ("email.dangerous_attachment", "email", r"^dangerous attachment \("),
    ("email.protected_archive", "email", r"^password-protected archive attachment \("),
    ("email.archive_attachment", "email", r"^archive attachment \("),
    ("email.missing_message_id", "email", r"^missing Message-ID header$"),
    ("email.no_received_chain", "email", r"^no Received headers"),
    ("email.long_delivery_chain", "email", r"^unusual delivery path \(\d+ hops\)$"),
    ("email.html_only", "email", r"^HTML-only body with no plain-text alternative$"),
    # --- QR -----------------------------------------------------------------
    ("qr.payment_payload", "qr", r"^payment QR payload \("),
    ("qr.link_benign", "qr", r"^QR link decodes to "),
    ("qr.link", "qr", r"^QR link "),
    ("qr.mailto", "qr", r"^QR payload opens an email compose window"),
    ("qr.tel", "qr", r"^QR payload dials a phone number"),
    ("qr.plain_text", "qr", r"^QR payload is plain text"),
    # --- text ---------------------------------------------------------------
    ("text.payment_uri", "text", r"^payment URI in the message text"),
    ("text.tel_uri", "text", r"^click-to-dial tel: link in the message text"),
)

_COMPILED: Tuple[Tuple[str, str, "re.Pattern"], ...] = tuple(
    (code, family, re.compile(pattern)) for code, family, pattern in REGISTRY
)

DESCRIPTIONS: Dict[str, str] = {
    "url.no_https": "Link is plain HTTP",
    "url.embedded_credentials": "Credentials embedded in the URL",
    "url.at_masking": "@-sign used to mask the real host",
    "url.ip_host": "Raw IP address instead of a domain",
    "url.punycode": "Punycode (IDN) hostname",
    "url.non_ascii_host": "Non-ASCII characters in the hostname",
    "url.many_subdomains": "Unusually many subdomain labels",
    "url.multiple_hyphens": "Multiple hyphens in the domain",
    "url.long_hostname": "Very long hostname",
    "url.long_url": "Very long URL",
    "url.suspicious_tld": "Suspicious TLD",
    "url.shortener": "URL shortener hides the destination",
    "url.brand_foreign_domain": "Brand name on a non-official domain",
    "url.brand_leet": "Look-alike brand spelling (digits swapped)",
    "url.brand_typosquat": "Possible typosquat of a brand",
    "url.credential_path": "Credential-themed path segment",
    "phone.premium_rate": "Premium-rate number",
    "phone.digit_pattern": "Repeated or sequential digits",
    "phone.brand_country_mismatch": "Brand named with a foreign country code",
    "phone.messaging_app": "Contact routed through a messaging app",
    "phone.urgency_callback": "Urgency plus a request to call",
    "phone.national_callback": "National-format callback number",
    "phone.tel_link": "Click-to-dial link",
    "phone.multiple_numbers": "Several contact numbers in one message",
    "email.no_auth_results": "No Authentication-Results header",
    "email.spf_fail": "SPF failed",
    "email.dkim_fail": "DKIM failed",
    "email.dmarc_fail": "DMARC failed",
    "email.reply_to_mismatch": "Reply-To differs from From domain",
    "email.return_path_mismatch": "Return-Path differs from From domain",
    "email.display_name_spoof": "Display name claims a brand it cannot own",
    "email.sender_domain_risk": "Sender domain is itself risky",
    "email.dangerous_attachment": "Executable or script attachment",
    "email.protected_archive": "Password-protected archive attachment",
    "email.archive_attachment": "Archive attachment",
    "email.missing_message_id": "Missing Message-ID header",
    "email.no_received_chain": "No Received headers",
    "email.long_delivery_chain": "Unusually long delivery path",
    "email.html_only": "HTML-only body",
    "qr.payment_payload": "Payment (scan-to-pay) QR payload",
    "qr.link": "QR payload is a flagged link",
    "qr.link_benign": "QR payload is a link with no URL signals",
    "qr.mailto": "QR payload opens a mail composer",
    "qr.tel": "QR payload dials a number",
    "qr.plain_text": "QR payload is plain text",
    "text.payment_uri": "Payment URI (UPI/crypto) in the message text",
    "text.tel_uri": "Click-to-dial tel: link in the message text",
}


def all_codes() -> List[str]:
    return [code for code, _family, _pattern in REGISTRY]


def known_codes() -> set:
    return set(all_codes())


def family_of(code: str) -> str:
    return code.split(".", 1)[0]


def code_for_signal(signal: str) -> Optional[str]:
    """Map one human-readable signal to its stable code (None if unregistered)."""
    text = (signal or "").strip()
    for code, _family, pattern in _COMPILED:
        if pattern.search(text):
            return code
    return None


def codes_for_signals(signals: Iterable[str]) -> Dict[str, List[str]]:
    """Return {codes, unmapped} for a list of human-readable signals."""
    codes: List[str] = []
    unmapped: List[str] = []
    for signal in signals or []:
        code = code_for_signal(signal)
        if code is None:
            unmapped.append(signal)
        elif code not in codes:
            codes.append(code)
    return {"codes": codes, "unmapped": unmapped}


def describe(code: str) -> str:
    return DESCRIPTIONS.get(code, code)