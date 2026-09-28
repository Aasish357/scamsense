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
3. Apply the initial migration:
   ```bash
   # If using Supabase CLI
   supabase db push
   ```
   Or copy the SQL statements directly from `supabase/migrations/20260928000001_init.sql` into the SQL Editor and execute.
4. The migration will create:
   - `users`: table for user credentials and profiles with unique constraints on `username` and `email`.
   - `analyses`: table storing text/screenshot analysis results keyed by `analysis_id`.
   - `feedback`: table recording user submissions.
   - Row-Level Security (RLS) policies and performance indexes for each table.
5. In your Supabase dashboard under **Project Settings > API**, locate:
   - `Project URL` (`SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_URL`)
   - `anon public` key (`NEXT_PUBLIC_SUPABASE_ANON_KEY`)
   - `service_role secret` key (`SUPABASE_SERVICE_ROLE_KEY` — server only, keep private)

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
4. Render will build using the root `Dockerfile` (which includes OCR system libraries like `tesseract-ocr`) and run healthchecks at `/health`.

### Option B: Railway
1. In [Railway](https://railway.app), create a new project from your repo.
2. Railway detects `Dockerfile` and `railway.json`.
3. Add the environment variables (`CORS_ORIGINS`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `PORT`).
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

---

## 3. Frontend Deployment (Vercel)

1. Import the repository into [Vercel](https://vercel.com).
2. Set the **Root Directory** to `apps/web` (or keep root with `vercel.json`).
3. Add Environment Variables in Project Settings:
   - `NEXT_PUBLIC_API_BASE_URL`: URL of the deployed FastAPI backend (e.g. `https://scamsense-api.onrender.com`).
   - `NEXT_PUBLIC_SUPABASE_URL`: Supabase Project URL.
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`: Supabase Anonymous Public Key.
4. Deploy.

### CORS Configuration Note
Ensure the backend's `CORS_ORIGINS` environment variable includes your production Vercel domain without trailing slashes:
```
CORS_ORIGINS=https://scamsense.vercel.app,https://your-custom-domain.com
```
