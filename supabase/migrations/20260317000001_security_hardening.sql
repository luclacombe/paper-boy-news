-- Security hardening: RLS on feed_stats + function search_path fixes
-- Addresses Supabase security advisor findings

-- 1. Enable RLS on feed_stats (global table, but should not be writable via anon/authenticated)
-- Service role key (used by build runner) bypasses RLS, so upserts still work.
ALTER TABLE public.feed_stats ENABLE ROW LEVEL SECURITY;

-- Allow anyone to read feed stats (used by web app for reading time estimates)
CREATE POLICY "Anyone can read feed stats"
  ON public.feed_stats
  FOR SELECT
  USING (true);

-- 2. Fix mutable search_path on SECURITY DEFINER function (prevents search_path injection)
ALTER FUNCTION public.handle_new_user() SET search_path = public;

-- 3. Fix mutable search_path on trigger function
ALTER FUNCTION public.update_updated_at() SET search_path = public;
