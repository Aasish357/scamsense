# ScamSense Product Overview

## User Journey
1. User opens ScamSense.
2. Chooses one of four analysis modes: **text/URL**, **screenshot**, **email headers**, or **QR code**.
3. Submits the content (typed, pasted, or uploaded).
4. Receives a risk assessment with a score, evidence and a recommended action.
5. Understands the evidence and what it does — and does not — prove.
6. Optionally saves (signed in), reports or gives feedback.

## What each mode checks

| Mode | Deterministic checks before the AI step |
|---|---|
| Text / URL | link structure, homoglyph/punycode hosts, suspicious TLDs, shorteners, brand lookalikes, IP hosts, `@`-masking, credential-themed paths, phone numbers |
| Screenshot | upload signature/size/dimensions, OCR text, local vision transcription, embedded QR payloads |
| Email headers | SPF/DKIM/DMARC verdicts, Reply-To and Return-Path mismatch, display-name brand spoofing, lookalike sender domain, risky attachments, delivery-trace gaps |
| QR code | local decode, payload scored as a link, "scan to pay" schemes (`upi://`, `bitcoin:`, ...) |

## Scope status
- **Shipped (MVP)**: guest checks, URL analysis, screenshots, local-AI explanations, auth with saved history, feedback/reports, minimal admin console.
- **Shipped (Phase 2)**: email-header analysis, phone-number risk signals, local QR decoding.
- **Not shipped**: voice/deepfake call analysis, regional-language support, hosted threat-intel feeds, billing. Unimplemented modes are not shown in the UI — never simulated.