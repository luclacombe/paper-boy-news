-- Add OPDS token column for wireless sync (KOReader)
ALTER TABLE user_profiles ADD COLUMN opds_token TEXT;

-- Unique index (prevents token collisions), only for non-null tokens
CREATE UNIQUE INDEX idx_user_profiles_opds_token
  ON user_profiles (opds_token)
  WHERE opds_token IS NOT NULL;
