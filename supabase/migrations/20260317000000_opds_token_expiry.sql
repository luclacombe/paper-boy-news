-- Add expiry timestamp for OPDS tokens (90-day default)
ALTER TABLE public.user_profiles
ADD COLUMN opds_token_expires_at timestamptz;

-- Set expiry for existing tokens (90 days from now)
UPDATE public.user_profiles
SET opds_token_expires_at = now() + interval '90 days'
WHERE opds_token IS NOT NULL;
