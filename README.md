# ScamSense

**Know Before You Trust.**

ScamSense is a web application that helps ordinary people evaluate suspicious text messages, links, and screenshots *before* they lose money, credentials, or privacy. It returns an evidence-grounded risk assessment — not a verdict — and tells the user what is known, what isn't, and what to do next.

> ScamSense is a decision-support tool. It does not guarantee safety or fraud, and it is not a substitute for verifying with the organization a message claims to be from.

**Status:** The MVP is implemented for text/message analysis, passive URL analysis, screenshot extraction, local-AI explanations, auth with saved history, feedback/reports and a minimal admin console. Email, phone, QR, voice and billing are not implemented. The table below reflects the code, not a roadmap.

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
  → Choose text, URL, or screenshot
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
| Deterministic, versioned risk scoring | ✅ Implemented (`heuristic_index` / `local-1`; also the offline fallback for the AI path) |
| Screenshot upload + OCR | ✅ Implemented — Tesseract when installed, local vision-model fallback |
| AI-assisted, evidence-grounded explanations | ✅ Implemented — local Ollama + RAG over a scam-pattern corpus |
| Brand verification registry | 🟡 Starter registry only (3 brands, backend route, no UI surface) |
| Isolated active URL fetching | ⚠️ Not implemented — all URL analysis is passive/local |
| Auth & saved history | ✅ Implemented — password auth, signed bearer tokens, per-user history |
| Reports, feedback, admin console | ✅ Implemented — `POST /reports`, feedback, `/admin` behind `ADMIN_API_KEY` |
| Billing | ❌ Not in MVP scope |
| Email / phone / QR / voice analysis | ⚠️ Not implemented (Phase 2+; not shown in UI) |

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
- An unavailable provider is not a clean reputation result — it's missing coverage.
- A failed analysis is an error state, never a zero (low-risk) score.
- Results can be `complete`, `partial`, or `insufficient_evidence` (null score, null level).
- Every signal carries an evidence classification: **Observed** (from submitted content or a completed check), **Reputation** (from an identified provider), or **Inference** (an interpretation of observed evidence) — and inferences are never presented as facts.

## Architecture

```
                         ┌─────────────────────┐
                         │   apps/web (Next.js) │
                         │  PWA shell, TS, Tailwind
                         └──────────┬───────────┘
                                    │ HTTPS / OpenAPI-typed client
                         ┌──────────▼───────────┐
                         │ services/api (FastAPI)│
                         │  routes · auth · risk │
                         │  analysis · providers │
                         └───┬───────────┬───────┘
              ┌──────────────┘           └───────────────┐
   ┌──────────▼──────────┐                    ┌───────────▼────────────┐
   │ services/fetcher     │                    │ AI provider interface   │
   │ isolated URL fetch   │                    │ (OpenAI, constrained)   │
   │ SSRF-hardened, no JS │                    │ extraction / explanation│
   └──────────────────────┘                    └─────────────────────────┘
                                    │
                         ┌──────────▼───────────┐
                         │ Supabase (Postgres)   │
                         │ Auth · RLS · Storage   │
                         └────────────────────────┘
```

Design principles:

- **Modular monolith**, not microservices — one web app, one backend, with a separately isolated boundary for active URL fetching.
- **Risk logic is isolated** from API orchestration, AI providers, and presentation, so scoring stays deterministic and testable independent of the model.
- **Untrusted input everywhere**: messages, URLs, fetched pages, screenshots, OCR output, and threat-feed text are all treated as hostile and never become model instructions.
- **Fail closed**: unavailable dependencies produce explicit "unavailable" states, never substituted or invented results.

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), plain JavaScript, inline styles + global CSS |
| Backend | Python 3.7+, FastAPI |
| Database | PostgreSQL (Supabase) with in-memory fallback for local development |
| Auth | Custom password auth (PBKDF2-SHA256) + HMAC-signed bearer tokens |
| AI | Local Ollama (`phi3:mini` chat, `moondream` vision, `nomic-embed-text` embeddings) + RAG |
| Frontend hosting | Vercel |
| Backend hosting | Container (Dockerfile installs Tesseract OCR) |
| URL analysis | Passive/lexical only — no fetcher service exists |

## Repository Structure

```
scamsense/
  apps/
    web/
      src/app/            # Next.js pages (/, /check, /history, /register, /feedback, /admin, /results/[id])
      src/app/api/        # FastAPI backend (main.py + routers, risk engine, RAG, Ollama client)
      src/lib/            # apiClient with token handling
      tests/e2e/          # Playwright full-flow script (full_flow.js)
  supabase/
    migrations/           # users, analyses, feedback, reports, ownership columns
  tests/
    unit/                 # pytest suite (API, auth/ownership, URL analysis, uploads, RAG)
  docs/
    product.md
    architecture.md
    security-privacy.md
    evaluation.md
    deployment.md
  infrastructure/
```

## API

All endpoints are versioned under `/api/v1`.

```
POST   /analyze                 # extract signals + links -> RAG retrieval -> local Ollama LLM
POST   /check                   # deterministic heuristic analysis (used as offline fallback)
POST   /screenshot              # image -> text/links via OCR or local vision model
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
type AssessmentStatus = "complete" | "partial" | "insufficient_evidence";

interface AnalysisResult {
  schema_version: string;
  analysis_id: string;
  assessment_status: AssessmentStatus;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  score_kind: "heuristic_index" | "llm_rag_index";
  scoring_version: string;
  summary: string;
  signals: EvidenceSignal[];
  coverage: DetectorCoverage[];
  recommended_actions: SafeAction[];
  limitations: string[];
  locale: string;
  created_at: string;
}
```

## Getting Started

> Prerequisites: Node.js 20+, Python 3.7+ (3.11+ recommended), and optionally a Supabase project. For AI-assisted explanations, run a local [Ollama](https://ollama.com) server with the models listed under Environment Variables (`phi3:mini`, `moondream`, `nomic-embed-text`). Without Ollama, analysis falls back to deterministic heuristics.

```bash
# 1. Clone
git clone https://github.com/<your-org>/scamsense.git
cd scamsense

# 2. Frontend
cd apps/web
npm install
cp .env.example .env.local   # fill in Supabase + API URL
npm run dev

# 3. Backend (in a separate terminal)
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # fill in DB, Supabase, provider keys
uvicorn app.main:app --reload

# 4. Database
supabase db push             # applies migrations in supabase/migrations
```

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

# End-to-end browser flow (Playwright)
# Requires the backend on :8000 and the frontend on :3000
cd apps/web && node tests/e2e/full_flow.js
```

Detection quality (precision/recall/F1, false-positive/negative rate, latency, cost per analysis) is not yet measured — there is no evaluation harness in this repository. Scores are heuristic indices, not calibrated probabilities.

## Security & Privacy

- URL analysis is passive and local: URLs are parsed and scored lexically (never fetched, no DNS lookups, no JavaScript execution, no page content retrieval).
- Screenshot uploads are validated by file signature (not extension), size- and dimension-bounded, processed in memory, and never written to disk or object storage.
- Ownership is enforced server-side: history lists only the signed-in user's analyses, and reads/deletes of owned records require the owner's bearer token. Guest analyses are readable by anyone holding the analysis id — a deliberate MVP limitation.
- Auth tokens are HMAC-SHA256 signed with `AUTH_SECRET`, carry a 7-day expiry, and are rejected when tampered with or expired.
- The admin console requires `ADMIN_API_KEY`; when unset the admin API responds 503 rather than being silently open.
- Raw message content, credentials, and images are never written to logs by the application.

Full threat model: `docs/security-privacy.md`.

## Roadmap

**Phase 2** — QR analysis, dedicated email analysis, phone-number risk signals, Hindi/Telugu support, expanded threat intel, "Ask ScamSense" assistant, consent-based family accounts.

**Phase 3** — Native mobile apps, share-to-ScamSense, browser extension, email integrations, opt-in alerts, privacy-preserving aggregate intelligence (ScamSense Radar).

**Phase 4** — Evaluated call-related and voice/deepfake signals (with explicit limitations, never claimed as proof), business API, bank/telecom integrations.

Each future capability requires its own threat model and acceptance criteria before it ships — see `docs/product.md`.

## Contributing

Issues and PRs are welcome once the repository is public. Please read `docs/architecture.md` and `docs/security-privacy.md` before proposing changes to the risk engine or URL fetcher — those paths have hard security requirements (see above) that PRs must not weaken.

## Disclaimer

ScamSense provides guidance, not a guarantee of safety or fraud. It does not authenticate images, confirm caller identity, block payments, or contact your bank. Always verify suspicious communications independently through an organization's official, verified channel.

## License

_TBD — add a `LICENSE` file before making the repository public._
