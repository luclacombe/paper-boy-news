-- Migration: Replace Gmail API + SMTP email delivery with Resend
-- Renames kindle_email → recipient_email (used for all email-based delivery, not just Kindle)
-- Drops SMTP configuration columns (no longer needed — Resend uses API key from env)

-- Rename kindle_email to recipient_email
ALTER TABLE public.user_profiles
  RENAME COLUMN kindle_email TO recipient_email;

-- Drop SMTP/Gmail method columns
ALTER TABLE public.user_profiles
  DROP COLUMN IF EXISTS email_method,
  DROP COLUMN IF EXISTS email_smtp_host,
  DROP COLUMN IF EXISTS email_smtp_port,
  DROP COLUMN IF EXISTS email_sender,
  DROP COLUMN IF EXISTS email_password;
