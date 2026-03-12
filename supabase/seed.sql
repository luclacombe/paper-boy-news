-- Seed data for local development
-- Creates test users via Supabase Auth + populates profiles, feeds, and delivery history
--
-- Test accounts (all passwords: "password123"):
--   dev@paperboy.local       — fresh user (onboarding NOT complete)
--   onboarded@paperboy.local — fully onboarded with feeds + delivery history

-- ══════════════════════════════════════════════════════════
-- Test user 1: Fresh user (pre-onboarding)
-- ══════════════════════════════════════════════════════════

-- Create auth user (the on_auth_user_created trigger auto-creates the profile)
INSERT INTO auth.users (
  instance_id, id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at, confirmation_token, recovery_token,
  email_change_token_new, email_change
) VALUES (
  '00000000-0000-0000-0000-000000000000',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'authenticated', 'authenticated',
  'dev@paperboy.local',
  crypt('password123', gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}', '{}',
  now(), now(), '', '', '', ''
);

-- Also insert into auth.identities (required by Supabase Auth)
INSERT INTO auth.identities (
  id, provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  jsonb_build_object('sub', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'email', 'dev@paperboy.local'),
  'email',
  now(), now(), now()
);

-- ══════════════════════════════════════════════════════════
-- Test user 2: Onboarded user with feeds + history
-- ══════════════════════════════════════════════════════════

INSERT INTO auth.users (
  instance_id, id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at, confirmation_token, recovery_token,
  email_change_token_new, email_change
) VALUES (
  '00000000-0000-0000-0000-000000000000',
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'authenticated', 'authenticated',
  'onboarded@paperboy.local',
  crypt('password123', gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}', '{}',
  now(), now(), '', '', '', ''
);

INSERT INTO auth.identities (
  id, provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at
) VALUES (
  gen_random_uuid(),
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  jsonb_build_object('sub', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'email', 'onboarded@paperboy.local'),
  'email',
  now(), now(), now()
);

-- Wait for trigger to create profile, then update it
-- (trigger fires synchronously, so profile exists by now)

-- Get the auto-created profile ID and update it
UPDATE public.user_profiles SET
  title = 'The Morning Paper',
  device = 'kobo',
  delivery_method = 'local',
  reading_time = '20 min',
  total_article_budget = 7,
  include_images = true,
  delivery_time = '06:00',
  timezone = 'America/New_York',
  google_drive_folder = 'Rakuten Kobo',
  onboarding_complete = true,
  opds_token = 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'
WHERE auth_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';

-- Add feeds for onboarded user
WITH profile AS (
  SELECT id FROM public.user_profiles
  WHERE auth_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
)
INSERT INTO public.user_feeds (user_id, name, url, category, position) VALUES
  ((SELECT id FROM profile), 'BBC News', 'https://feeds.bbci.co.uk/news/rss.xml', 'World', 0),
  ((SELECT id FROM profile), 'Reuters', 'https://www.reutersagency.com/feed/', 'World', 1),
  ((SELECT id FROM profile), 'Hacker News', 'https://hnrss.org/frontpage', 'Tech', 2),
  ((SELECT id FROM profile), 'Ars Technica', 'https://feeds.arstechnica.com/arstechnica/index', 'Tech', 3),
  ((SELECT id FROM profile), 'The Verge', 'https://www.theverge.com/rss/index.xml', 'Tech', 4);

-- Add sample delivery history for onboarded user
WITH profile AS (
  SELECT id FROM public.user_profiles
  WHERE auth_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
)
INSERT INTO public.delivery_history (
  user_id, status, edition_number, edition_date,
  article_count, source_count, file_size, file_size_bytes,
  delivery_method, delivery_message, sections
) VALUES
  (
    (SELECT id FROM profile), 'delivered', 1,
    to_char(now() - interval '2 days', 'YYYY-MM-DD'),
    24, 5, '1.2 MB', 1258291, 'local', 'Downloaded successfully',
    '[{"name":"World","headlines":["Global summit concludes","Markets rally"]},{"name":"Tech","headlines":["New AI model released","Startup raises $50M"]}]'::jsonb
  ),
  (
    (SELECT id FROM profile), 'delivered', 2,
    to_char(now() - interval '1 day', 'YYYY-MM-DD'),
    18, 5, '980 KB', 1003520, 'local', 'Downloaded successfully',
    '[{"name":"World","headlines":["Election results in","Peace talks begin"]},{"name":"Tech","headlines":["Open source project hits 1M stars"]}]'::jsonb
  ),
  (
    (SELECT id FROM profile), 'failed', 3,
    to_char(now(), 'YYYY-MM-DD'),
    0, 0, '0 KB', 0, 'local', '',
    NULL
  );
