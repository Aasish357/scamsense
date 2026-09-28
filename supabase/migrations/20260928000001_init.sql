-- Supabase Schema Migration: ScamSense MVP
-- Tables: users, analyses, feedback

-- 1. Create tables
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.analyses (
    analysis_id TEXT PRIMARY KEY,
    risk_score INTEGER,
    risk_level TEXT,
    score_kind TEXT NOT NULL DEFAULT 'heuristic_index',
    scoring_version TEXT NOT NULL DEFAULT 'local-1',
    summary TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommendation JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS public.feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 2. Indexes for frequent lookups
CREATE INDEX IF NOT EXISTS idx_users_username ON public.users (username);
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users (email);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON public.analyses (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON public.feedback (created_at DESC);

-- 3. Enable Row Level Security (RLS)
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feedback ENABLE ROW LEVEL SECURITY;

-- 4. Policies for Service Role (backend full access)
-- Note: the service_role key automatically bypasses RLS in Supabase, but explicit policies ensure clarity.
CREATE POLICY "service_role_all_users"
    ON public.users
    AS PERMISSIVE
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "service_role_all_analyses"
    ON public.analyses
    AS PERMISSIVE
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "service_role_all_feedback"
    ON public.feedback
    AS PERMISSIVE
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- 5. Public read/guest policies for anon/authenticated if accessed directly via Supabase client
-- Allow anon/authenticated to read analyses
CREATE POLICY "anon_read_analyses"
    ON public.analyses
    AS PERMISSIVE
    FOR SELECT
    TO anon, authenticated
    USING (true);

-- Allow anon/authenticated to submit feedback
CREATE POLICY "anon_insert_feedback"
    ON public.feedback
    AS PERMISSIVE
    FOR INSERT
    TO anon, authenticated
    WITH CHECK (true);
