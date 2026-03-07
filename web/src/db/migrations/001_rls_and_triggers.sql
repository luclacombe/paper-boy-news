-- Phase 1.2: Row Level Security policies + auto-profile trigger
-- Run this in Supabase SQL Editor or via: psql $DATABASE_URL -f this_file.sql

-- ══════════════════════════════════════════════════════════
-- RLS: user_profiles
-- ══════════════════════════════════════════════════════════

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own profile"
  ON user_profiles FOR SELECT
  USING (auth_id = auth.uid());

CREATE POLICY "Users update own profile"
  ON user_profiles FOR UPDATE
  USING (auth_id = auth.uid());

CREATE POLICY "Users insert own profile"
  ON user_profiles FOR INSERT
  WITH CHECK (auth_id = auth.uid());

-- ══════════════════════════════════════════════════════════
-- RLS: user_feeds
-- ══════════════════════════════════════════════════════════

ALTER TABLE user_feeds ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own feeds"
  ON user_feeds FOR ALL
  USING (
    user_id IN (
      SELECT id FROM user_profiles WHERE auth_id = auth.uid()
    )
  );

-- ══════════════════════════════════════════════════════════
-- RLS: delivery_history
-- ══════════════════════════════════════════════════════════

ALTER TABLE delivery_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own history"
  ON delivery_history FOR ALL
  USING (
    user_id IN (
      SELECT id FROM user_profiles WHERE auth_id = auth.uid()
    )
  );

-- ══════════════════════════════════════════════════════════
-- Auto-create profile on signup
-- ══════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.user_profiles (auth_id)
  VALUES (new.id);
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Drop existing trigger if re-running
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ══════════════════════════════════════════════════════════
-- Auto-update updated_at timestamp
-- ══════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at
  BEFORE UPDATE ON user_profiles
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
