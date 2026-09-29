-- ============================================================================
-- ScamSense - complete database schema
--
-- This is the four migrations in supabase/migrations/ combined into one
-- script, in dependency order. It is safe to run more than once: every object
-- is created with IF NOT EXISTS and every policy is dropped first.
--
-- Order matters: the owner/modality columns are added BEFORE the indexes that
-- use them.
-- ============================================================================

-- --- 1. Tables -------------------------------------------------------------
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

CREATE TABLE IF NOT EXISTS public.reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL DEFAULT 'guest',
    analysis_id TEXT,
    reason TEXT NOT NULL,
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- --- 2. Columns added after the tables -------------------------------------
-- LLM + RAG pipeline, ownership, and the email / phone / QR modality fields.
ALTER TABLE public.analyses
    ADD COLUMN IF NOT EXISTS schema_version TEXT NOT NULL DEFAULT '2026-09-28',
    ADD COLUMN IF NOT EXISTS assessment_status TEXT NOT NULL DEFAULT 'complete',
    ADD COLUMN IF NOT EXISTS engine TEXT NOT NULL DEFAULT 'heuristic_fallback',
    ADD COLUMN IF NOT EXISTS llm_model TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS extracted_links JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS extracted_emails JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS rag_context JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS owner TEXT,
    ADD COLUMN IF NOT EXISTS modality TEXT NOT NULL DEFAULT 'text',
    ADD COLUMN IF NOT EXISTS extracted_phones JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS email_findings JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS qr_payloads JSONB NOT NULL DEFAULT '[]'::jsonb;

-- --- 3. Indexes (after the columns they use exist) ------------------------
CREATE INDEX IF NOT EXISTS idx_users_username ON public.users (username);
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users (email);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON public.analyses (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyses_owner ON public.analyses (owner);
CREATE INDEX IF NOT EXISTS analyses_modality_created_at_idx ON public.analyses (modality, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON public.feedback (created_at DESC);

-- --- 4. Row Level Security -------------------------------------------------
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;

-- --- 5. Policies -----------------------------------------------------------
-- The backend's secret key acts as service_role and bypasses RLS; these make
-- that explicit. The browser never talks to Supabase directly.
DROP POLICY IF EXISTS "service_role_all_users" ON public.users;
CREATE POLICY "service_role_all_users"
    ON public.users AS PERMISSIVE FOR ALL TO service_role
    USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_analyses" ON public.analyses;
CREATE POLICY "service_role_all_analyses"
    ON public.analyses AS PERMISSIVE FOR ALL TO service_role
    USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_feedback" ON public.feedback;
CREATE POLICY "service_role_all_feedback"
    ON public.feedback AS PERMISSIVE FOR ALL TO service_role
    USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_reports" ON public.reports;
CREATE POLICY "service_role_all_reports"
    ON public.reports AS PERMISSIVE FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- Guest read of analyses and public feedback, in case anything ever connects
-- directly with the publishable key.
DROP POLICY IF EXISTS "anon_read_analyses" ON public.analyses;
CREATE POLICY "anon_read_analyses"
    ON public.analyses AS PERMISSIVE FOR SELECT TO anon, authenticated
    USING (true);

DROP POLICY IF EXISTS "anon_insert_feedback" ON public.feedback;
CREATE POLICY "anon_insert_feedback"
    ON public.feedback AS PERMISSIVE FOR INSERT TO anon, authenticated
    WITH CHECK (true);