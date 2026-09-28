-- Add columns used by the LLM + RAG analysis pipeline (/analyze endpoint).

ALTER TABLE public.analyses
    ADD COLUMN IF NOT EXISTS schema_version TEXT NOT NULL DEFAULT '2026-09-28',
    ADD COLUMN IF NOT EXISTS assessment_status TEXT NOT NULL DEFAULT 'complete',
    ADD COLUMN IF NOT EXISTS engine TEXT NOT NULL DEFAULT 'heuristic_fallback',
    ADD COLUMN IF NOT EXISTS llm_model TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS extracted_links JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS extracted_emails JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS rag_context JSONB NOT NULL DEFAULT '[]'::jsonb;