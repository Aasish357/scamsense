# ScamSense

**Know Before You Trust.**

ScamSense is a web application that helps ordinary people evaluate suspicious text messages, links, and screenshots *before* they lose money, credentials, or privacy. It returns an evidence-grounded risk assessment — not a verdict — and tells the user what is known, what isn't, and what to do next.

> ScamSense is a decision-support tool. It does not guarantee safety or fraud, and it is not a substitute for verifying with the organization a message claims to be from.

**Status:** Early-stage MVP. See [Implementation Status](#implementation-status) below — this README documents the target architecture, not a finished product.

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
| Guest text/message analysis | 🚧 Milestone 1 |
| Passive URL analysis (lexical, no active fetch) | 🚧 Milestone 1 |
| Deterministic, versioned risk scoring | 🚧 Milestone 1 |
| Screenshot upload + OCR | ⏳ Milestone 2 |
| AI-assisted, evidence-grounded explanations | ⏳ Milestone 2 |
| Brand verification registry | ⏳ Milestone 2 |
| Isolated active URL fetching | ⏳ Milestone 2 (gated on security review) |
| Auth (email + Google) & saved history | ⏳ Milestone 3 |
| Reports, feedback, admin console | ⏳ Milestone 3 |
| Billing | ❌ Not in MVP scope |
| Email / phone / QR / voice analysis | ❌ Phase 2+ (not shown in UI until real) |

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
| 0–20 | | Low Risk |
| 21–40 | | Caution |
| 41–60 | | Suspicious |
| 61–80 | | High Risk |
| 81–100 | | Very High Risk |

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
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python, FastAPI |
| Database | PostgreSQL (Supabase) |
| Auth | Supabase Auth (email + Google) |
| Object storage | Private Supabase Storage |
| AI | OpenAI, behind a provider abstraction |
| Cache/Queue | Redis (only if/when justified) |
| Frontend hosting | Vercel |
| Backend hosting | Container / serverless (TBD) |
| URL fetcher | Isolated execution boundary, separate from the main API |

## Repository Structure

```
scamsense/
  apps/
    web/                  # Next.js frontend (PWA shell)
  services/
    api/
      app/
        routes/
        auth/
        analysis/
        risk/
        providers/
        security/
    fetcher/               # Isolated active URL-fetch boundary
  packages/
    contracts/             # Shared API/type contracts
    ui/                    # Shared UI components
  supabase/
    migrations/
    seed/
  tests/
    unit/
    integration/
    e2e/
    security/
    evaluations/
  docs/
    product.md
    architecture.md
    security-privacy.md
    evaluation.md
  infrastructure/
```

## API

All endpoints are versioned under `/api/v1`.

```
POST   /api/v1/analyze/text
POST   /api/v1/analyze/url
POST   /api/v1/analyze/image

GET    /api/v1/analyses/{analysis_id}
DELETE /api/v1/analyses/{analysis_id}
GET    /api/v1/me/analyses

POST   /api/v1/reports
POST   /api/v1/feedback
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
  score_kind: "heuristic_index";
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

> Prerequisites: Node.js 20+, Python 3.11+, a Supabase project, and an OpenAI API key for full functionality. Core text/URL checks work without the AI key using deterministic detectors only.

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
# apps/web
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_BASE_URL=

# services/api
DATABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=      # server-side only, never shipped to the client
OPENAI_API_KEY=                 # optional — degrades to deterministic-only mode if unset
THREAT_INTEL_API_KEY=           # optional — reputation checks disabled if unset
```

Missing credentials disable the dependent feature and surface an honest "unavailable" state — they never fall back to invented results.

## Testing

```bash
# Frontend
cd apps/web && npm test

# Backend
cd services/api && pytest tests/unit tests/integration

# End-to-end
npm run test:e2e

# Security suite (SSRF, auth, upload validation, prompt injection)
pytest tests/security
```

Detection quality (precision/recall/F1, false-positive/negative rate, abstention rate, latency, cost per analysis) is tracked separately from software correctness against a governed evaluation set — see `tests/evaluations/` and `docs/evaluation.md`.

## Security & Privacy

- Submitted URLs are treated as hostile: no active fetch until the isolated fetcher passes SSRF/DNS-rebinding tests; no JavaScript execution, form submission, or credential/cookie use; redirects and destinations are revalidated at connection time; cloud metadata and internal networks are blocked.
- Suspicious URLs render as non-clickable text everywhere in the product.
- Screenshots are validated by file signature (not extension), size- and dimension-bounded, stripped of metadata, stored privately, and deleted after processing.
- Ownership is enforced server-side on every read/write/delete; guest access uses scoped, short-lived tokens rather than a bare analysis ID.
- Raw message content, credentials, full URLs, and images are never written to logs or sent to analytics/session-replay tools.
- Retention periods are defined per data type (uploads, guest results, saved analyses, reports, logs) and enforced with real deletion, not policy text alone.

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
