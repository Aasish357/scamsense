# ScamSense Security & Privacy Requirements

## Threat model

ScamSense ingests hostile input by design: the submitted text, email, URL or image is attacker-controlled and must never be trusted, executed or treated as instructions.

| Threat | Mitigation |
|---|---|
| Prompt injection through submitted content | Submitted content is passed as quoted data below a Message to analyze boundary, and the prompt states explicitly that it must be analyzed and never followed as instructions. There is no tool-calling or code-execution path for submitted text, so an injected instruction has no action to take. |
| SSRF / active fetching | URL analysis is **lexical only**. URLs are parsed and scored; they are never fetched, resolved or executed. |
| Malicious uploads (huge, polyglot, malformed images) | Validated by **magic bytes** (not extension or client MIME), size-capped (8 MB), dimension-capped (10k per side, 40 MP), decoded in memory, never written to disk. |
| Zip-bomb / decompression bombs | No archive is ever extracted; attachments are only inspected by name suffix. `.eml` uploads are capped at 2 MB. |
| Third-party data leakage | QR codes are decoded **in-process** with OpenCV — no external scanner API. Email headers are parsed **offline** — no DNS lookups to validate SPF/DKIM/DMARC. AI runs against a **local Ollama** server. No hosted AI provider receives user content. |
| Credential theft via impersonation | Attachment suffixes (`.exe`, `.scr`, `.js`, ...) are flagged; display-name brand spoofing and sender-domain lookalikes are detected and reported. |
| Unauthorised data access | Analyses are ownership-scoped: history and deletes require the owner's bearer token. Guest analyses are readable by anyone holding the `analysis_id` — a deliberate, documented MVP limitation. |
| Admin surface exposure | Admin routes require `ADMIN_API_KEY`; when unset the API returns 503 rather than silently opening. |
| Log leakage | Raw content, credentials and images are never written to application logs. |
| Resource exhaustion via LLM | LLM calls have explicit timeouts and degrade to the deterministic engine. |
| Assistant leaking data it should not have | The assistant receives only the sanitized fields of one stored analysis (never raw message text or images, which are not persisted) plus public scam-pattern text. Questions are capped at 500 characters, scoped to a single analysis id, and inherit that analysis' ownership check. |

## Access controls
- HMAC-SHA256 signed bearer tokens (`AUTH_SECRET`), 7-day expiry, rejected when tampered with or expired.
- Passwords hashed with PBKDF2-HMAC-SHA256 (120,000 iterations, per-user salt) using only the standard library.
- Per-user scoping on history, delete and report endpoints.
- CORS restricted to a configured allowlist.

## Privacy principles
- **Data minimisation**: only extracted signals (links, emails, phones, payload text, attachments names) are stored — not raw uploads.
- **Local by default**: no image or email leaves the machine; the only outbound traffic is to a local Ollama server the user runs themselves.
- **Transparency**: the result states which modality produced it, which engine scored it (heuristic vs LLM) and which version of the rules was used.

## Known limitations
- Header-based SPF/DKIM/DMARC verdicts reflect what the submitting mail client reported. Headers can be stripped or forged; treat authentication findings as strong *indicators*, not proof.
- QR decoding can fail on heavily degraded, distorted or partially occluded codes — a 422 means "no code decoded", not "safe".
- Lexical URL scoring cannot detect a compromised legitimate domain.