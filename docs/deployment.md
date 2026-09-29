# Deployment Guide

This document describes how to deploy the **ScamSense** stack to production.

## Architecture Overview

- **Frontend**: Next.js App Router (deployed to **Vercel**).
- **Backend API**: Python / FastAPI (containerized with **Docker**, deployable to **Render**, **Railway**, or **Fly.io**).
- **Database & Auth**: **Supabase** (PostgreSQL with Row-Level Security).

---

## 1. Database Setup (Supabase)

1. Create a project at [supabase.com](https://supabase.com).
2. Go to the **SQL Editor** in your Supabase project dashboard.
3. Apply all migrations in order (files in `supabase/migrations/`):
   ```bash
   # If using Supabase CLI
   supabase db push
   ```
   Or paste each file into the SQL Editor and execute them in sequence:
   - `20260928000001_init.sql` - core tables and RLS policies
   - `20260928000002_analysis_llm_fields.sql` - LLM/RAG analysis columns
   - `20260928000003_auth_ownership_and_reports.sql` - ownership and reports
   - `20260928000004_analysis_modalities.sql` - `modality`, `extracted_phones`, `email_findings`, `qr_payloads`
4. The migrations will create:
   - `users`: table for user credentials and profiles with unique constraints on `username` and `email`.
   - `analyses`: table storing text/URL, screenshot, email and QR analysis results keyed by `analysis_id` (see the `modality` column).
   - `feedback`: table recording user submissions.
   - `reports`: table recording user-flagged analyses for admin review.
   - Row-Level Security (RLS) policies and performance indexes for each table.
5. In your Supabase dashboard under **Project Settings > API**, locate:
   - **Project URL** (`SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_URL`)
   - **anon public** key (`NEXT_PUBLIC_SUPABASE_ANON_KEY`)
   - **service_role secret** key (`SUPABASE_SERVICE_ROLE_KEY` - server only, keep private)

---

## 2. Backend Deployment (FastAPI)

### Option A: Render
1. Connect your GitHub repository to [Render](https://render.com).
2. Create a new **Web Service** or use **Blueprint** pointing to `render.yaml`.
3. Set Environment Variables:
   - `PORT`: `8000`
   - `CORS_ORIGINS`: Comma-separated list of allowed origins, e.g. `https://your-frontend.vercel.app,http://localhost:3000`
   - `SUPABASE_URL`: Your Supabase Project URL.
   - `SUPABASE_SERVICE_ROLE_KEY`: Your Supabase Service Role Key.
   - `AUTH_SECRET`: Secret used to sign auth tokens.
4. Render will build using the root `Dockerfile` (which installs the OCR and OpenCV system libraries) and run healthchecks at `/health`.

### Option B: Railway
1. In [Railway](https://railway.app), create a new project from your repo.
2. Railway detects `Dockerfile` and `railway.json`.
3. Add the environment variables (`CORS_ORIGINS`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `AUTH_SECRET`, `PORT`).
4. Generate a public domain (e.g. `https://scamsense-api.up.railway.app`).

### Option C: Docker / VPS
Build and run locally or on a VPS:
```bash
docker compose up --build -d
```
Verify the API:
```bash
curl http://localhost:8000/health
```

### Python dependencies
`apps/web/requirements.txt` includes `opencv-python-headless` (local QR decoding) and `pytesseract` (OCR).
The headless OpenCV wheel needs no GUI libraries; the `Dockerfile` already installs the shared
runtime libraries (`libgl1`, `libglib2.0-0`) and `tesseract-ocr`.

> If `opencv-python-headless` cannot be installed in your environment, the rest of ScamSense keeps
> working: `/analyze/qr` returns HTTP 422 ("No QR code could be decoded") and screenshot analysis
> simply skips QR extraction.

---

## 3. Frontend Deployment (Vercel)

> Vercel hosts the **Next.js frontend only**. The FastAPI backend cannot run on
> Vercel (it needs a long-running ASGI server), so deploy section 2 first and
> point the frontend at it. Order matters: without a backend URL the UI still
> loads, but every check reports the API as offline.

1. Import the repository into [Vercel](https://vercel.com) and pick the
   `scamsense` project.
2. **Set the Root Directory to `apps/web`.** This is the one setting that
   matters: the Next.js app lives in `apps/web`, so Vercel must look there.
   Leave "Framework Preset" on *Next.js* (auto-detected) and the build/install
   commands at their defaults (`npm install`, `npm run build`).
   There is deliberately **no** `vercel.json` at the repository root: pointing
   Vercel at the root would look for a Next.js app that does not exist there.
3. Add Environment Variables under *Project Settings > Environment Variables*
   (add them for **Production**, **Preview** and **Development**):
   - `NEXT_PUBLIC_API_BASE_URL`: the deployed backend URL, e.g.
     `https://scamsense-api.onrender.com` (no trailing slash).
   - `NEXT_PUBLIC_SUPABASE_URL`: Supabase Project URL (optional - without it
     history stays in memory and is lost on restart).
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`: Supabase Anonymous Public Key.
4. Deploy. The build runs `npm install && npm run build` inside `apps/web` and
   the app is served at `https://<project>.vercel.app`.
5. Back on the backend (Render/Railway), set `CORS_ORIGINS` to the Vercel URL so
   the browser is allowed to call it:

   ```
   CORS_ORIGINS=https://<project>.vercel.app
   ```

6. Smoke test the live deployment: open the app, run one clearly benign message
   (expect *low* / 0) and one obvious phishing string (expect a high score and
   named evidence). If the header shows "FastAPI Backend: offline", the URL or
   CORS is wrong.

### Deploying from the CLI instead

```bash
cd apps/web
npx vercel --prod --token "$VERCEL_TOKEN"     # production
npx vercel --token "$VERCEL_TOKEN"             # preview
```

A token is created in Vercel under *Settings > Tokens*. The Vercel CLI is not
installed in this environment, so CLI deploys need `npx` (which downloads it) or
a global `npm i -g vercel`.

### CORS Configuration Note
Ensure the backend's `CORS_ORIGINS` environment variable includes your production Vercel domain without trailing slashes:
```
CORS_ORIGINS=https://scamsense.vercel.app,https://your-custom-domain.com
```