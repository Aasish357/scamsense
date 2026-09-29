# ScamSense

**Know Before You Trust.**

ScamSense is a web application that helps ordinary people evaluate suspicious text messages, links, and screenshots *before* they lose money, credentials, or privacy. It returns an evidence-grounded risk assessment — not a verdict — and tells the user what is known, what isn't, and what to do next.

> ScamSense is a decision-support tool. It does not guarantee safety or fraud, and it is not a substitute for verifying with the organization a message claims to be from.

**Status:** Shipped: text/URL analysis, passive lexical URL engine, screenshot extraction, email/header analysis, phone-number risk signals, local QR decoding, the Ask ScamSense assistant, an installable PWA with share-to-ScamSense, a browser extension, auth with saved history, feedback/reports and a minimal admin console. Not implemented: active URL fetching, regional languages, threat-intel feeds, voice/deepfake analysis and billing. The table below reflects the code, not a roadmap.

---

## Table of Contents

- [Why ScamSense](#why-scamsense)
- [Core User Journey](#core-user-journey)
- [Implementation Status](#implementation-status)
- [How Risk Is Assessed](#how-risk-is-assessed)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [API](#api)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [Security & Privacy](#security--privacy)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)
- [License](#license)

---

## Why ScamSense

Scam messages, phishing links, and doctored screenshots are getting harder for ordinary people to evaluate on their own. ScamSense gives a user a fast, evidence-based second opinion:

1. **What was detected?**
2. **What evidence supports the assessment?**
3. **What remains unknown?**
4. **What could happen if I proceed?**
5. **What should I do next?**
6. **How can I verify this independently?**

ScamSense never presents an AI assessment as proof of safety or fraud. When evidence is insufficient, it says so explicitly instead of guessing.

## Core User Journey

```
Open ScamSense
  → Choose text/URL, screenshot, email headers, or QR code
  → Submit content
  → See meaningful progress
  → Receive a supported assessment
  → Understand the evidence and limitations
  → Take a safer next action
  → Optionally save, report, or give feedback
```

No account is required to run a check. Accounts are only needed to save history.

## Implementation Status

| Capability | Status |
|---|---|
| Guest text/message analysis | ✅ Implemented |
| Passive URL analysis (lexical, no active fetch) | ✅ Implemented — structure, homoglyph/punycode, suspicious TLD, shortener, brand-lookalike checks |
| Deterministic, versioned risk scoring | ✅ Implemented (`heuristic_index` / `local-2`; also the offline fallback for the AI path) |
| Screenshot upload + OCR | ✅ Implemented — Tesseract when installed, local vision-model fallback |
| QR code decoding | ✅ Implemented — decoded locally with OpenCV, payload scored for lookalike domains and "scan to pay" (upi://) codes |
| Email / header analysis | ✅ Implemented — SPF/DKIM/DMARC verdicts, Reply-To / Return-Path mismatch, display-name spoofing, risky attachments |
| Phone-number risk signals | ✅ Implemented — premium-rate lines, brand/country mismatch, messaging-app routing, pressure to call back |
| AI-assisted, evidence-grounded explanations | ✅ Implemented — local Ollama + RAG over a scam-pattern corpus |
| Ask ScamSense assistant | ✅ Implemented — follow-up questions answered from the stored analysis + retrieved patterns; never sees the original message |
| Installable PWA + share-to-ScamSense | ✅ Implemented — web app manifest, icons, offline page, and a share target that accepts text, links and images |
| Browser extension (MV3) | ✅ Implemented — check a selection, link or page from the context menu; toolbar badge shows the risk score |
| Evaluation harness | ✅ Implemented — labelled corpus, per-detector precision/recall/F1, end-to-end false-alarm rate, gated in CI |
| Brand verification registry | 🟡 Starter registry only (3 brands, backend route, no UI surface) |
| Isolated active URL fetching | ⚠️ Not implemented — all URL analysis is passive/local |
| Auth & saved history | ✅ Implemented — password auth, signed bearer tokens, per-user history |
| Reports, feedback, admin console | ✅ Implemented — `POST /reports`, feedback, `/admin` behind `ADMIN_API_KEY` |
| Billing | ❌ Not in MVP scope |
| Voice / deepfake call analysis | ⚠️ Not implemented (Phase 4; not shown in UI) |

The home screen only ever exposes analysis modes that are actually implemented. A missing capability is disabled and disclosed — never simulated.

## How Risk Is Assessed

ScamSense produces a **heuristic risk index**, not a calibrated probability.

```
Input validation → Normalization → Entity extraction
  → Deterministic detectors → Reputation checks (if available)
  → Validated AI-assisted observations → Evidence normalization
  → Evidence-sufficiency check → Versioned score aggregation
  → Explanation generation → Safe-action selection
```

| Band | Score | Label |
|---|---|---|
| Score | Level |
|---|---|
| 0–19 | Low |
| 20–49 | Caution |
| 50–69 | Suspicious |
| 70–84 | High |
| 85–100 | Very high |

Displayed as *"High Risk — 72/100 risk index"*, never as *"72% chance this is a scam."*

Rules that hold across the engine:

- No evidence is not evidence of safety.
- An unavailable provider is not a clean result — it is missing coverage, and the response says which engine actually ran (`engine`, `llm_model`).
- A failed analysis is an error state, never a zero (low-risk) score: bad input returns 4xx, an undecodable QR returns 422, an empty share returns 400.
- `assessment_status` is `complete` today; `partial` and `insufficient_evidence` are reserved values, not yet emitted.
- Deterministic findings are always included in the evidence, even when the local model produced its own reasoning — the user always sees what the rules found.

## Architecture

```
                 phone share sheet          browser toolbar
                        |                        |
                        v                        v
        +---------------------------------------------+
        |  apps/extension (MV3)  /  apps/web (Next.js PWA)   <- presentation
        +---------------------------------------------+
                        |  HTTPS (JSON / multipart)
                        v
        +---------------------------------------------+
        |  apps/web/src/app/api  (FastAPI)                |
        |  routes - auth - risk engine - analyzers        |
        |  phone / email / QR / URL detectors - RAG       |
        +----------------------+----------------------+
                               |  http, localhost only
                               v
                    +----------------------+
                    |  Local Ollama          |
                    |  chat + vision + embed  |
                    +----------------------+

        +---------------------------------------------+
        |  Supabase (Postgres) - analyses, users,       |
        |  feedback, reports   |  in-memory fallback     |
        +---------------------------------------------+
```

Design principles:

- **Modular monolith**, not microservices: one web app whose `src/app/api` directory *is* the FastAPI backend, plus the extension and the service worker as thin clients of it.
- **Risk logic is isolated** from API orchestration, AI providers, and presentation, so scoring stays deterministic and testable independent of the model.
- **Untrusted input everywhere**: messages, URLs, emails, screenshots, OCR output, QR payloads and the assistant's questions are all treated as hostile and never become model instructions.
- **Fail closed**: unavailable dependencies produce explicit "unavailable" states, never substituted or invented results. When Ollama is offline the deterministic engine answers and the response says so.
- **Local by default**: no hosted AI provider, no URL fetcher, no DNS lookups. The only outbound traffic is to an Ollama server the user runs.

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), plain JavaScript, inline styles + global CSS |
| Backend | Python 3.7+, FastAPI |
| Database | PostgreSQL (Supabase) with in-memory fallback for local development |
| Auth | Custom password auth (PBKDF2-SHA256) + HMAC-signed bearer tokens |
| AI | Local Ollama (`phi3:mini` chat, `moondream` vision, `nomic-embed-text` embeddings) + RAG |
| Frontend hosting | Vercel |
| Backend hosting | Render, native Python runtime (no container). Tesseract is not installable there, so screenshot OCR is unavailable in production and the analysis falls back to its deterministic path |
| URL analysis | Passive/lexical only — no fetcher service exists |

## Repository Structure

```
scamsense/
  apps/
    extension/            # Manifest V3 browser extension (no build step)
      background.js       #   service worker: context menus, /analyze call, badge
      popup.*             #   verdict panel
    web/
      public/             # manifest.webmanifest, sw.js, generated icons
      src/app/            # Next.js pages (/, /check, /history, /register,
                          #   /feedback, /admin, /offline, /results/[id], /share)
      src/app/api/        # the FastAPI backend (main.py + routers, risk engine,
                          #   URL/phone/email/QR analyzers, RAG, Ollama client)
      src/lib/            # apiClient (token handling), shareTarget (IndexedDB)
      tests/e2e/          # Playwright: full_flow.js, extension_check.js
      requirements.txt    # backend dependencies (pillow, opencv-headless, ...)
  supabase/
    migrations/           # users, analyses, feedback, reports, LLM + modality columns
  tests/
    unit/                 # pytest suite (API, auth/ownership, uploads, URL, phone,
                          #   email, QR, assistant, RAG)
  scripts/
    generate_icons.py     # regenerates the PWA and extension icon sets
  docs/
    product.md
    architecture.md
    security-privacy.md
    evaluation.md
    deployment.md
  infrastructure/
```

## API

Analysis and system routes are unversioned; the stored-record, account and
reporting routes also answer under `/api/v1`.

```
POST   /analyze                 # extract signals + links -> RAG retrieval -> local Ollama LLM
POST   /check                   # deterministic heuristic analysis (used as offline fallback)
POST   /screenshot              # image -> text/links via OCR or local vision model (+ local QR decode)
POST   /analyze/email           # raw email (headers + body) -> authentication + spoofing signals -> LLM
POST   /analyze/email/upload    # same, from an uploaded .eml / .txt file
GET    /analyze/email/findings  # header-level findings only, no LLM call
POST   /analyze/qr              # image -> locally decoded QR payload -> LLM
POST   /assistant/ask           # follow-up question answered from the stored analysis (+ RAG)
GET    /llm/health              # local Ollama availability and configured models

GET    /api/v1/analyses/{analysis_id}
DELETE /api/v1/analyses/{analysis_id}
GET    /api/v1/me/analyses

POST   /api/v1/reports
POST   /reports
POST   /api/v1/feedback

POST   /register
POST   /login

GET    /admin/overview           # requires the x-admin-key header (ADMIN_API_KEY)
```

Only endpoints backing implemented features are exposed — there are no placeholder routes that return fake results. Result payloads follow a shared TypeScript/Pydantic contract:

```ts
type RiskLevel = "low" | "caution" | "suspicious" | "high" | "very_high";
type Modality = "text" | "screenshot" | "email" | "qr";

// The shape returned by /check, /screenshot, /analyze, /analyze/email,
// /analyze/qr and /assistant/ask (mirrors the Pydantic models).
interface AnalysisResult {
  schema_version: string;          // "2026-09-28"
  analysis_id: string;
  assessment_status: string;       // "complete" today; "partial" / "insufficient_evidence" are reserved
  risk_score: number;              // 0-100 heuristic index, never a probability
  risk_level: RiskLevel;
  score_kind: "heuristic_index" | "llm_rag_index";
  scoring_version: string;         // e.g. "local-2" or "ollama-phi3:mini+rag-1"
  summary: string;
  evidence: string | string[];     // deterministic findings are always included
  recommendation: string | string[];
  created_at: string;
  engine: "heuristic_fallback" | "ollama_rag";
  llm_model: string;               // empty when the local AI was offline
  modality: Modality;              // which input path produced this result
  extracted_links: string[];
  extracted_emails: string[];
  extracted_phones: string[];
  rag_context?: { title: string; category: string; score: number; text: string }[];
  qr_payloads?: string[];          // QR modality
  email_findings?: object;         // email modality: header signals + parsed fields
}
```

## Getting Started

> Prerequisites: Node.js 20+, Python 3.7+ (3.11+ recommended), and optionally a Supabase project. For AI-assisted explanations, run a local [Ollama](https://ollama.com) server with the models listed under Environment Variables (`phi3:mini`, `moondream`, `nomic-embed-text`). Without Ollama, analysis falls back to deterministic heuristics.

```bash
# 1. Clone
git clone https://github.com/Aasish357/scamsense.git
cd scamsense

# 2. Backend (FastAPI lives in apps/web/src/app/api)
cd apps/web
python -m venv .venv && .venv/Scripts/activate        # Windows; use source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python -m uvicorn apps.web.src.app.main:app --port 8000 --reload   # or, from apps/web: uvicorn src.app.main:app --port 8000

# 3. Frontend (in a second terminal)
cd apps/web
npm install
cp .env.example .env.local        # set NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm run dev

# 4. Database (optional - the app falls back to in-memory storage)
supabase db push                  # applies every migration in supabase/migrations

# 5. Browser extension (optional)
#    chrome://extensions -> Developer mode -> Load unpacked -> apps/extension
```

Regenerate the icon sets (PWA + extension) with `python scripts/generate_icons.py`.

## Environment Variables

No secrets are committed. See `.env.example` in each app for the full list. At minimum:

```
# apps/web (frontend)
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000

# Backend
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
SUPABASE_URL=                   # optional — falls back to in-memory storage when unset
SUPABASE_SERVICE_ROLE_KEY=      # server-side only, never shipped to the client
AUTH_SECRET=                    # signs auth tokens; random per-process fallback when unset
ADMIN_API_KEY=                  # enables /admin/overview; disabled (503) when unset

# Local AI (optional — /analyze degrades to deterministic heuristics when offline)
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=phi3:mini
OLLAMA_VISION_MODEL=moondream
OLLAMA_EMBED_MODEL=nomic-embed-text:latest
```

Missing credentials disable the dependent feature and surface an honest "unavailable" state — they never fall back to invented results.

## Testing

```bash
# Backend unit/API tests (run from the repository root)
python -m pytest tests

# Evaluation harness: per-detector precision/recall/F1 + end-to-end metrics
python scripts/evaluate.py                     # full report
python scripts/evaluate.py --update-baseline   # accept the current numbers
python scripts/evaluate.py --external          # also score datasets in corpus/external/

# End-to-end browser flow (Playwright)
# Requires the backend on :8000 and the frontend on :3000
cd apps/web && node tests/e2e/full_flow.js      # 11 steps, needs a local Ollama

# Browser extension (loads the real MV3 extension into Chromium)
cd apps/web && node tests/e2e/extension_check.js
```

Current baseline: **84 unit tests**, **11/11 E2E steps** and **5/5 extension checks** passing, with a live local Ollama (`phi3:mini`).

**Measured detector quality** over the committed 90-sample labelled corpus
(`corpus/`, see `docs/evaluation-report.md`):

| Metric | Value |
|---|---|
| Scam detection rate | 100% (40/40) |
| False-alarm rate on benign | 0% (0/50) |
| Benign samples scoring >= 50 | 0% |
| Mean risk index, scam / benign | 78.5 / 2.3 |
| Median latency per sample | ~0.1 ms text, 0.3 ms email, ~22 ms QR (encode+decode) |

The corpus is deliberately synthetic and every host in it is unroutable
(`.example`/`.test`/`.invalid`), so these numbers measure **the detectors**, not
the difficulty of real-world scams, and they are *not* a claim about live
accuracy. `.github/workflows/evaluation.yml` fails the build when any of these
metrics regress against `corpus/baseline.json`.

## Security & Privacy

- URL analysis is passive and local: URLs are parsed and scored lexically (never fetched, no DNS lookups, no JavaScript execution, no page content retrieval).
- Screenshot uploads are validated by file signature (not extension), size- and dimension-bounded, processed in memory, and never written to disk or object storage.
- QR codes are decoded in-process with OpenCV: the image is never sent to a third-party scanner, and only the decoded text payload enters the analysis pipeline.
- Email analysis is offline too — SPF/DKIM/DMARC verdicts are read from the `Authentication-Results` / `Received-SPF` headers already present in the submitted message; no DNS lookups are performed. `.eml` uploads are capped at 2 MB.
- The browser extension requests no host beyond the configured ScamSense API: it ships with permission for a local backend only, asks for a remote host only when you point it at one, and has no analytics, no remote code and no update server. It sends nothing about the page you are on.
- Share-to-ScamSense runs entirely on-device: the service worker parks a shared message, link or image in IndexedDB, and the user reviews it in the form before anything is sent. Nothing is uploaded by the share action itself, and the worker never caches analysis traffic or cross-origin requests.
- The assistant answers from stored signals only: raw message text and images are never persisted, so a follow-up question cannot quote content the user has already deleted. Answers carry a fixed "second opinion, not proof" disclaimer, and access follows the same ownership rule as reading the analysis.
- Ownership is enforced server-side: history lists only the signed-in user's analyses, and reads/deletes of owned records require the owner's bearer token. Guest analyses are readable by anyone holding the analysis id — a deliberate MVP limitation.
- Auth tokens are HMAC-SHA256 signed with `AUTH_SECRET`, carry a 7-day expiry, and are rejected when tampered with or expired.
- The admin console requires `ADMIN_API_KEY`; when unset the admin API responds 503 rather than being silently open.
- Raw message content, credentials, and images are never written to logs by the application.

Full threat model: `docs/security-privacy.md`.

## Roadmap

**Phase 2 (shipped)** — QR analysis, dedicated email/header analysis, phone-number risk signals, "Ask ScamSense" assistant.

**Phase 2 (remaining)** — Hindi/Telugu support, expanded threat intel, consent-based family accounts.

**Phase 3 (shipped)** — PWA foundation (manifest, icons, offline fallback) and share-to-ScamSense for text, links and images.

**Phase 3 (shipped, cont.)** — browser extension (Manifest V3) for checking a selection, link or page in place.

**Phase 3 (remaining)** — native mobile apps, email integrations, opt-in alerts, privacy-preserving aggregate intelligence (ScamSense Radar).

**Phase 4** — Evaluated call-related and voice/deepfake signals (with explicit limitations, never claimed as proof), business API, bank/telecom integrations.

Each future capability requires its own threat model and acceptance criteria before it ships — see `docs/product.md`.

## Contributing

Issues and PRs are welcome once the repository is public. Please read `docs/architecture.md` and `docs/security-privacy.md` before proposing changes to the risk engine or URL fetcher — those paths have hard security requirements (see above) that PRs must not weaken.

## Disclaimer

ScamSense provides guidance, not a guarantee of safety or fraud. It does not authenticate images, confirm caller identity, block payments, or contact your bank. Always verify suspicious communications independently through an organization's official, verified channel.

## License

_TBD — add a `LICENSE` file before making the repository public._
