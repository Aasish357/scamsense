-- MVP completion: per-user ownership + reports table.

ALTER TABLE public.analyses
    ADD COLUMN IF NOT EXISTS owner TEXT;

CREATE INDEX IF NOT EXISTS idx_analyses_owner ON public.analyses (owner);

CREATE TABLE IF NOT EXISTS public.reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL DEFAULT 'guest',
    analysis_id TEXT,
    reason TEXT NOT NULL,
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_reports"
    ON public.reports
    AS PERMISSIVE
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);