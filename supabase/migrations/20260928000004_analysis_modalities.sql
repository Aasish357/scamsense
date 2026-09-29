-- Modality columns for the email, phone and QR analysis pipelines.

ALTER TABLE public.analyses
    ADD COLUMN IF NOT EXISTS modality TEXT NOT NULL DEFAULT 'text',
    ADD COLUMN IF NOT EXISTS extracted_phones JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS email_findings JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS qr_payloads JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS analyses_modality_created_at_idx
    ON public.analyses (modality, created_at DESC);