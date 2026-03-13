-- Feed statistics table: observed per-feed metrics from builds.
-- Global (not per-user) — keyed by feed URL.
-- Written by build_for_users.py (service role), read by Drizzle (direct DB).

CREATE TABLE IF NOT EXISTS public.feed_stats (
  url text PRIMARY KEY,
  name text NOT NULL,
  observed_at timestamptz NOT NULL DEFAULT now(),
  sample_count integer NOT NULL DEFAULT 1,

  -- Latest observation
  total_entries integer NOT NULL DEFAULT 0,
  fresh_24h integer NOT NULL DEFAULT 0,
  fresh_48h integer NOT NULL DEFAULT 0,
  attempted integer NOT NULL DEFAULT 0,
  extracted integer NOT NULL DEFAULT 0,
  avg_word_count real NOT NULL DEFAULT 0,
  median_word_count real NOT NULL DEFAULT 0,
  avg_images real NOT NULL DEFAULT 0,

  -- Derived rolling averages (recomputed on each upsert from history)
  articles_per_day real NOT NULL DEFAULT 0,
  estimated_read_min real NOT NULL DEFAULT 0,
  daily_read_min real NOT NULL DEFAULT 0,

  -- Last 30 daily observations for rolling average computation
  history jsonb NOT NULL DEFAULT '[]'
);

-- No RLS — this table is only accessed via service role (build script)
-- and Drizzle ORM (direct DATABASE_URL connection, bypasses RLS).
