# ScamSense Architecture Overview

## Components

- **Frontend**: Next.js App Router (`apps/web`) — guest checks, account/history, feedback, admin console.
- **Backend**: Python FastAPI (`apps/web/src/app`) — routes, auth, risk engine, analysis providers.
- **Database**: PostgreSQL via Supabase for analyses, users, feedback and reports. Falls back to an in-process store when Supabase is not configured.
- **AI Integration**: a **local Ollama server** (chat + vision + embedding models). No hosted AI provider is used; when Ollama is offline the deterministic engine answers.
- **Deterministic analyzers**: pure-Python signal modules (`url_analysis`, `phone_analysis`, `email_analysis`, `qr_analysis`, `extraction`) that run before any model call.

## Analysis modalities

Every modality converges on the same pipeline, so results, history and reporting stay comparable:

```
input (text/URL | screenshot | raw email | QR image)
  -> modality parser        (extraction / screenshot OCR+vision / email stdlib parsing / OpenCV QR decode)
  -> deterministic detectors (URL, phone, email-header, QR-payload signals + suggested score)
  -> RAG retrieval          (local embeddings over the scam-pattern corpus; skipped when Ollama is offline)
  -> local LLM assessment   (grounded JSON: score, summary, evidence, recommendation)
  -> normalize + persist    (deterministic findings are always merged into the evidence)
  -> AnalysisResult         (modality + score + evidence + recommendation)
```

`modality` (`text`, `screenshot`, `email`, `qr`) is carried from input to storage so a result always states which analysis path produced it.

## Module map (backend)

| Module | Responsibility |
|---|---|
| `main.py` | FastAPI app, CORS, router registration |
| `api/check.py` | deterministic heuristics, shared record builder, risk bands |
| `api/llm_analyze.py` | extract -> RAG -> LLM pipeline, result normalization, prompt |
| `api/url_analysis.py` | passive lexical URL scoring (never fetches) |
| `api/phone_analysis.py` | phone extraction signals (premium rate, brand/country mismatch, callback pressure) |
| `api/email_analysis.py` | RFC 5322 parsing, SPF/DKIM/DMARC verdicts, spoofing and attachment signals |
| `api/qr_analysis.py` | local QR decode (OpenCV) and payload scoring |
| `api/screenshot.py` | upload validation, OCR / vision transcription, QR decode |
| `api/modalities.py` | `/analyze/email`, `/analyze/email/upload`, `/analyze/email/findings`, `/analyze/qr` |
| `api/extraction.py` | link, email and phone extraction/normalization |
| `api/auth.py`, `api/store.py` | HMAC-signed tokens, ownership rules, Supabase/in-memory persistence |
| `api/rag.py`, `api/ollama_client.py` | local retrieval and model client |

## Data Flow

1. User picks a modality and submits content, a raw email or an image.
2. Frontend calls the matching endpoint (all share one result contract).
3. Backend runs deterministic analyzers, then RAG + local LLM when available.
4. Result is persisted (owner set when signed in) and returned.
5. Frontend renders score, evidence, recommendation and the input modality.