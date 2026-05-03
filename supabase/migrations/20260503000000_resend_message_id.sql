-- Email idempotency: durable proof-of-send.
--
-- After Resend's Emails.send returns, the build runner stores the response
-- id here. _deliver_record short-circuits when this column is non-null, so
-- a record can never produce more than one email even if delivery is
-- retried (manual re-run, future catch-up sweep, race condition).
--
-- Defense-in-depth pairing: the record UUID is also passed as Resend's
-- Idempotency-Key header, giving 24h server-side dedupe on top of this
-- DB-durable column.

ALTER TABLE delivery_history
  ADD COLUMN IF NOT EXISTS resend_message_id text;
