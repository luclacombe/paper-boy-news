-- Initial schema: tables, RLS policies, and triggers
-- Mirrors web-next/src/db/schema.ts + web-next/src/db/migrations/001_rls_and_triggers.sql

-- ══════════════════════════════════════════════════════════
-- Tables
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS public.user_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_id uuid NOT NULL UNIQUE,
  title text NOT NULL DEFAULT 'Morning Digest',
  language text NOT NULL DEFAULT 'en',
  max_articles_per_feed integer NOT NULL DEFAULT 10,
  reading_time text NOT NULL DEFAULT '20 min',
  include_images boolean NOT NULL DEFAULT true,
  device text NOT NULL DEFAULT 'kobo',
  delivery_method text NOT NULL DEFAULT 'local',
  google_drive_folder text NOT NULL DEFAULT 'Rakuten Kobo',
  kindle_email text DEFAULT '',
  email_method text DEFAULT 'gmail',
  email_smtp_host text DEFAULT 'smtp.gmail.com',
  email_smtp_port integer DEFAULT 465,
  email_sender text DEFAULT '',
  email_password text DEFAULT '',
  delivery_time text NOT NULL DEFAULT '06:00',
  timezone text NOT NULL DEFAULT 'UTC',
  google_tokens jsonb,
  onboarding_complete boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.user_feeds (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
  name text NOT NULL,
  url text NOT NULL,
  category text NOT NULL DEFAULT 'Custom',
  position integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.delivery_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
  status text NOT NULL,
  edition_number integer,
  edition_date text NOT NULL,
  article_count integer DEFAULT 0,
  source_count integer DEFAULT 0,
  file_size text DEFAULT '0 KB',
  file_size_bytes integer DEFAULT 0,
  delivery_method text DEFAULT '',
  delivery_message text DEFAULT '',
  error_message text,
  epub_storage_path text,
  sections jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ══════════════════════════════════════════════════════════
-- RLS policies
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

ALTER TABLE user_feeds ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own feeds"
  ON user_feeds FOR ALL
  USING (
    user_id IN (
      SELECT id FROM user_profiles WHERE auth_id = auth.uid()
    )
  );

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

-- ══════════════════════════════════════════════════════════
-- Storage bucket for EPUBs
-- ══════════════════════════════════════════════════════════

INSERT INTO storage.buckets (id, name, public)
VALUES ('editions', 'editions', false)
ON CONFLICT (id) DO NOTHING;
