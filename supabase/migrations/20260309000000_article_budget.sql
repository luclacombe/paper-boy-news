-- Rename max_articles_per_feed to total_article_budget
-- Per-feed limits replaced with total article budget system
ALTER TABLE public.user_profiles RENAME COLUMN max_articles_per_feed TO total_article_budget;
ALTER TABLE public.user_profiles ALTER COLUMN total_article_budget SET DEFAULT 7;
