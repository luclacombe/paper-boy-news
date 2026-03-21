# Source Budget Roadmap

Source selection / source delivery overhaul — 5-step initiative.

**Why:** The reading time setting was inaccurate (fixed article count mapping), sources had no frequency awareness, and the source selection UI is a long unintuitive checkbox wall.

## Step 1 — Feed frequency metadata ✅ (done)
- `feed_stats` Supabase table with `articles_per_day`, `estimated_read_min`, `daily_read_min`, 30-day rolling history
- `upsert_feed_stats()` pushes after every build, `getFeedStats()` / `getAllFeedStats()` server actions exist
- `seed_feed_stats.py` for initial population (needs a build or seed run before Step 3 deploys)

## Step 2 — Word-count-based budgeting ✅ (done)
- `apply_reading_time_budget()` uses word count / 238 WPM, scarcity-aware, 5-min overshoot cap
- `build_for_users.py` parses `reading_time` from DB. CLI falls back to `total_article_budget`

## Step 3 — Frequency-aware freshness & budget integration ✅ (done)
- `FeedConfig.articles_per_day` + `estimated_read_min` populated from `feed_stats` via `fetch_feed_stats_map()`
- `_freshness_window_days()`: prolific ≥3/day → 1.5d, moderate ≥0.5/day → 2d, scarce → 2-7d (scaled by article length), unknown → 7d
- `_is_stale_entry()` parameterized with per-feed window; budget uses real `articles_per_day`
- **Prerequisite for production:** run `seed_feed_stats.py --from-build` (or wait for a scheduled build) to populate initial data

## Step 4 — UI: Reading time estimates in source selection ✅ (done)
- Budget bar shows capped estimate: `min(sourceOutput, budget)` — realistic paper reading time, not raw source output
- Chips show per-article reading time (`estimatedReadMin`) + frequency label (Daily, Weekly, etc.)
- Bundle cards show source count + avg per-article time
- Uses `getAllFeedStats()` already built in Step 1

## Step 5 — UI: Source selection UX overhaul ✅ (done)
- Replaced checkbox accordion with selectable chip grid (`feed-chip.tsx` + `feed-chip-grid.tsx`)
- Category and frequency filter bar; grouping toggle (segmented control) inline with heading
- Each chip shows feed name + frequency label + per-article reading time

## Future (not yet planned)
- Cross-edition dedup (track delivered URLs per user) — prevents repeats for daily readers
- Weekly source "include once then drop" — needs dedup infrastructure first
