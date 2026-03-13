# src/paper_boy — Core Python Library

The core library that fetches RSS feeds, extracts articles, generates EPUBs, and handles delivery. Used by both the CLI and the GitHub Actions build runner.

## Stack

- **Python 3.9+**, built with setuptools (`pyproject.toml`)
- **feedparser** — RSS/Atom feed parsing
- **trafilatura** — Full article text extraction from URLs
- **ebooklib** — EPUB3 creation
- **Pillow** — Cover image generation (600x900px)
- **google-api-python-client** — Google Drive upload
- **click** — CLI framework
- **pyyaml** — Config file parsing
- **playwright** (optional) — Headless Chromium for Cloudflare-protected sites (FT)

## Install

```bash
pip install -e ".[dev]"    # Editable install with dev deps (pytest, httpx)
pip install -e ".[browser]"  # With Playwright (needed for FT extraction)
```

## CLI

```bash
paper-boy build                          # Build EPUB locally
paper-boy deliver                        # Build + deliver
paper-boy build --config my.yaml         # Custom config
paper-boy -v build                       # Verbose logging
```

## Module Structure

```
src/paper_boy/
├── __init__.py       # Package init (__version__, ContentCache export)
├── cache.py          # In-memory content cache (ContentCache, CacheStats)
├── cli.py            # Click CLI entry point (build, deliver commands)
├── config.py         # YAML config loading + validation (Config, FeedConfig w/ category, DeliveryConfig, EmailConfig)
├── feeds.py          # RSS fetching, article text extraction, image optimization, Section w/ category, FeedObservation stats collection
├── filters.py        # Post-extraction content filters (junk stripping, paywall detection, quality gate)
├── epub.py           # EPUB generation with category grouping, dividers, EPUB3 landmarks nav
├── cover.py          # Cover image generation (600x900px, category-aware labels)
├── delivery.py       # Delivery backends: Google Drive, email (SMTP/Send-to-Kindle), local
└── main.py           # Orchestration: fetch → build → deliver (returns BuildResult)
```

## Key Functions

- `main.build_newspaper(config, cache=None) → BuildResult` — Main pipeline: fetch feeds → build EPUB → return result. `BuildResult` includes `feed_observations` (pre-budget per-feed stats)
- `main.build_and_deliver(config, cache=None) → BuildResult` — Build + deliver EPUB
- `feeds.fetch_feeds(config, cache=None, seen_urls=None) → list[Section]` — Fetch all configured feeds, extract articles. Collects `FeedObservation` data as a side effect (retrieved via `get_feed_observations()`)
- `feeds.get_feed_observations() → list[FeedObservation]` — Returns per-feed stats from the last `fetch_feeds()` call (entry counts, freshness, word counts, extraction rates). Used by build pipeline to populate `feed_stats` table
- `cache.ContentCache` — In-memory cache for feed entries, article HTML, and image bytes
- `epub.build_epub(sections, config) → path` — Generate EPUB file
- `cover.generate_cover(title, sections, issue_date) → bytes` — Generate newspaper-style cover image (600x900 JPEG)
- `delivery.deliver(path, config)` — Deliver via configured method (Google Drive, email, local)

## Config Format

YAML-based (`config.yaml`), see `config.example.yaml` in project root:

```yaml
title: "Morning Digest"
language: en
total_article_budget: 7   # fallback: total articles across all feeds (each source gets at least 1)
reading_time_minutes: 20  # preferred: time-based budget using word count / 238 WPM
include_images: true
feeds:
  - name: "The Guardian"
    url: "https://www.theguardian.com/world/rss"
    category: "World News"       # Optional — enables category grouping in EPUB
delivery:
  method: google_drive           # google_drive | email | local
  google_drive_folder: "Rakuten Kobo"
  keep_days: 7
```

## Content Cache

`ContentCache` (`cache.py`) deduplicates network I/O when multiple users share the same RSS feeds during a scheduled build run. Three cache layers:

| Layer | Key | Value | Saves |
|-------|-----|-------|-------|
| Feed | `feed_url` | full `feed.entries` list | HTTP + XML parse |
| Article | `(article_url, include_images)` | trafilatura HTML or `None` | HTTP + NLP extraction |
| Image | `image_url` | raw downloaded bytes or `None` | HTTP download |

- In-memory only, scoped to a single `run_build_all()` invocation (or `run_scheduled()` legacy)
- All functions accept an optional `cache` param (default `None`) — backward compatible
- Article key includes `include_images` because trafilatura output differs based on this flag
- Image cache stores raw bytes (pre-optimization) since optimization settings may vary per user
- Failed extractions/downloads are cached as `None` to prevent retries
- `cache.log_stats()` logs hit/miss summary after each scheduled run

## Design Decisions

- **Bundled font**: Playfair Display (OFL-licensed variable TTF) in `src/paper_boy/fonts/`. Supports Regular through Black weights via `set_variation_by_name()`. Guarantees consistent cover rendering on all platforms including CI (no bitmap fallback). ~300KB, included as package data in `pyproject.toml`.
- **Cover layout**: Newspaper broadsheet style — double-rule masthead with auto-scaling title, red-accented lead headline, secondary headlines grouped by category (when available, else by feed name with deduplication). Masthead font scales down automatically for long titles.
- **EPUB structure**: Category-grouped layout when feeds have categories (web app builds), flat layout when no categories (CLI mode). Spine order: cover page → front page TOC → [category divider → [feed divider → articles]*]*. EPUB3 landmarks generated via `book.guide` + `epub3_landmark=True` write option (`cover`, `toc`, `bodymatter`) + EPUB2 guide for proper opening behavior across all e-readers. TOC uses `epub.Link` (not `epub.Section`) so NCX navPoints have valid `<content src>` attributes.
- **EPUB CSS**: Optimized for e-ink displays (minimum gray #555) — paragraph indent (except first), justified text, larger body font (1.05em), improved line-height (1.7). Avoids CSS Grid/Flexbox (unsupported on most e-readers). Three-level TOC hierarchy: categories (1.5em bold uppercase), sources (0.95em italic), articles (normal). Category dividers are dominant chapter openers (2.2em, 80% rules, page-break-before). Section dividers are subordinate (1.3em, 1px border). Front page uses `.front-title`/`.front-date` CSS classes. Article source shows domain only (`via theguardian.com`). Article dates normalized to human-readable format (`March 7, 2026`).
- EPUB3 format for universal e-reader support
- `calibre:series` metadata for Kobo series grouping, standard EPUB3 series for all devices
- Multi-strategy article extraction with fallback chain (`_extract_article_content`):
  0. Domain-specific handlers:
     - Washington Post (`_extract_wapo_article`): article-level handler. Googlebot UA + Google referrer + X-Forwarded-For headers to bypass paywall. Parses `__NEXT_DATA__` JSON for structured content (headlines, text, images, lists). RSS feeds at `feeds.washingtonpost.com/rss/{section}`. Interactive pages skipped. Technique from Calibre's `wash_post.recipe` by unkn0wn.
     - Bloomberg (`_fetch_bloomberg_feed` + `_extract_bloomberg_article`): feed-level handler, bypass RSS entirely, mobile app API. Section listing via nav API → article HTML from `/bw/news/stories/{id}`. Supports section feeds (`/markets`, `/technology`) and Businessweek magazine (`/businessweek`). CDN API returns gzip.
     - Reuters (`_fetch_reuters_feed` + `_extract_reuters_article`): feed-level handler, section listing + article detail as structured JSON
     - Scientific American (`_fetch_sciam_feed` + `_fetch_sciam_issue_articles`): feed-level handler, no RSS. Homepage → issue page → `__DATA__` JSON for article discovery. Standard trafilatura for extraction (S1 works). Monthly magazine, features sorted first. Technique from Calibre's `scientific_american.recipe` by Kovid Goyal.
     - Project Syndicate: article-level routing in `_extract_article_content()`. PS uses Poool registration wall (only teaser in HTML). Detected by `project-syndicate.org` domain, routes directly to `_extract_via_archive()` (skips S1–S3). Technique from Calibre recipe by unkn0wn.
     - Financial Times (`_extract_ft_articles`): feed-level handler. FT is behind Cloudflare bot protection (JS challenge blocks all programmatic HTTP clients). Uses Playwright headless Chromium to solve the challenge, then the outbrain UA (`Mozilla/5.0 (Java) outbrain`) grants full-text access. RSS feeds at `ft.com/{section}?format=rss` for article discovery. Requires optional `playwright` dependency (`pip install paper-boy[browser]`). Gracefully returns 0 articles if Playwright is not installed. Technique verified against Calibre's `financial_times.recipe` by unkn0wn. Pre-processing via `_clean_ft_html()` strips CMS elements (video, iframe, button, svg, Flourish charts, o-expander widgets), unwraps `<picture>` to `<img>`, flattens `n-content-layout` wrappers, removes empty `<li>` tags, and deduplicates figcaptions (prefers editorial captions over alt-text duplicates). Live blogs (title contains "Live:" or "liveblog") are skipped.
     - Business of Fashion (`_fetch_bof_feed`): feed-level handler. BoF's RSS feed is broken (500 Internal Server Error on Arc Publishing's outboundfeeds endpoint). Uses homepage scraping for article discovery (`/articles/*` links), then parses `Fusion.globalContent` JavaScript object (Arc Publishing platform, same `content_elements` structure as WaPo's `__NEXT_DATA__`). All articles serve full content regardless of `content_restrictions.content_code` (paywall is client-side JS only). No special UA or auth needed.
  1. Standard trafilatura (default UA) + Ars Technica pagination
  1.5. Re-fetch with browser UA (`_BROWSER_USER_AGENT`) — bypasses interstitials (e.g. Nature). Cookie-aware via `http.cookiejar.CookieJar` to persist cookies across redirect chains
  2. Re-fetch with bot UA (`outbrain` crawler) → trafilatura
  3. JSON-LD structured data extraction (`articleBody` / `text` fields)
  4. Archive.today proxy (`_extract_via_archive`) — soft-paywalled sites
  - HN self-posts (`news.ycombinator.com/item`) use RSS feed content directly
  - `MIN_ARTICLE_WORDS = 150` threshold to detect truncated/paywalled content
  - Inline paywall detection (`_has_paywall_markers`) runs after each strategy's word count check — prevents paywall teasers (e.g. FT's "Subscribe to unlock") from short-circuiting the fallback chain. Runs `strip_junk()` first to avoid Nature-style false positives
  - All paths normalised via `_normalize_html()` (strips empty tags, inline styles, NPR caption artifacts, zero-width Unicode chars, self-closing blocks, CMS alt-text figcaptions, Space.com bare "Article continues below" text, BBC "Published" bullet lists, Bloomberg empty ad divs, URL-only figcaptions; converts TEI table tags; flattens nested figures)
  - Falls back to RSS feed content if all strategies fail
- **Premium title pre-filtering**: `_is_premium_title()` skips entries with `STAT+` anywhere in the title (not just prefix — handles "Opinion: STAT+: ..." pattern). Prevents mixed free/premium feeds (like STAT News) from triggering the consecutive failure abort before free articles are reached.
- **Title-based pre-filtering**: `_should_skip_title()` skips non-journalism entries before extraction — corrections/errata notices, affiliate roundup posts (e.g. Electrek "Green Deals"), NASA webinar invites. Runs in `_fetch_single_feed()` before any network calls.
- **URL pattern pre-filtering**: `_should_skip_url()` skips URLs matching known non-article patterns — Nature research papers (`s41586-*`), ProPublica tools/projects (`projects.propublica.org`), NASA NESC technical papers, Smithsonian sponsored content. Runs in `_fetch_single_feed()` before extraction.
- **Word count cap**: `MAX_ARTICLE_WORDS = 10000` rejects database/tracker pages (e.g. Vogue's 24000-word "People Moves Tracker") that pass quality gates but aren't news articles.
- **Performance safeguards** (prevent wasted time on doomed extractions):
  - **Domain strategy hints**: `_DOMAIN_STRATEGY_HINTS` dict maps domains to the strategy level they should start at, skipping known-failing earlier strategies. Nature (`nature.com: 2`) skips S1 and starts at S1.5 (browser UA). **Important**: when `hint_start >= 2`, domain failure tracking is suppressed — hint-skipped strategies aren't real failures, so they must not trigger domain blocking (which would prevent the working strategy from running).
  - **Consecutive failure abort**: `_MAX_CONSECUTIVE_FAILURES = 3` — if 3 articles in a row fail extraction within a single feed, stop iterating that feed's entries. Counter resets on success. Per-feed overrides in `_CONSECUTIVE_FAILURE_OVERRIDES` (e.g. HN at 10, since it links to diverse external domains where failures are expected).
  - **Domain-level failure tracking**: `_domain_failures` dict tracks extraction failures per domain. After `_DOMAIN_FAILURE_THRESHOLD = 2` strategy-1 (trafilatura) failures, strategies 1.5–4 are skipped for all subsequent articles from that domain. Prevents Politico/Axios-style feeds from spending ~13s per doomed article on the full fallback chain. Reset via `_reset_domain_failures()` at the start of each `fetch_feeds()` call. **Important**: paywall teasers (S1 returns enough words but paywall detected) do NOT record domain failures — the site is accessible, it just needs a different UA (e.g. FT works via S2 bot UA).
  - **Faster redirect detection**: `_LimitedRedirectHandler` caps redirects at 5 (default 10). After opening, `_fetch_page()` checks the final URL for auth patterns (`idp.`, `/login`, `/authorize`, `/signin`, `/auth/`) and returns None immediately if detected. Prevents Nature's idp redirect loop from consuming ~6s per article.
- `_convert_graphics_to_imgs()` normalises TEI XML `<graphic>` tags to `<img>` before the image pipeline runs (trafilatura emits `<graphic>` instead of `<img>` with `output_format="html"`)
- `_strip_duplicate_title()` scans ALL `<h1>`/`<h2>` tags in extracted HTML and removes any that fuzzy-match the article title (case-insensitive, punctuation-stripped, HTML entity-aware, containment check in both directions) — prevents double headings since `epub.py` adds its own `<h1>` from `Article.title`. Handles figure-first layouts (The Verge, Dezeen, AP News) where the title heading isn't the first element
- `_downgrade_body_headings()` converts all remaining `<h1>` to `<h2>` in article body — epub.py owns the `<h1>` via `Article.title`, so body `<h1>` tags would create duplicate top-level headings
- `_dedup_consecutive_paragraphs()` removes consecutive duplicate `<p>` and heading blocks using lxml DOM comparison — fixes Foreign Policy/Eater paragraph duplication from trafilatura double-extraction
- **Content filtering pipeline** (`filters.py`): Runs after extraction, before image processing. Five general-purpose filters:
  - `strip_junk(html)` — removes boilerplate `<p>`/`<div>` blocks by matching entire paragraph text against `_JUNK_PATTERN_GROUPS` (organized by category: generic boilerplate, social CTAs, newsletter CTAs, Wired/Space.com/ScienceDaily, Fox News, Kiplinger Adviser Intel/subscription/magazine CTAs). Adding a pattern = appending one string to the right group.
  - `strip_sciencedaily_metadata(html)` — removes ScienceDaily metadata `<ul>` blocks (Date/Source/Summary/Share fields)
  - `strip_bbc_related(html)` — removes BBC "Related topics" trailing sections
  - `strip_section_junk(html)` — removes multi-element junk sections (heading + list/content). Uses lxml for DOM-aware stripping. Rules in `_SECTION_JUNK_RULES` list (18 rules: Read this next, Recommended Stories, Contact Us/Got a Tip?, Sign up to, Support Our Work/Donate, Subscribe/Sign up for Kiplinger, Related content/Read More, What we're reading, Behind the Scenes, Top comment by, On supporting science journalism, This story is funded by readers, About This Story, Get marketing news, From just...Kiplinger, Recommended newsletters for you). Three scope types: `to_end` (remove all after heading), `to_next_heading` (remove until next h2/h3/h4), `next_N` (remove heading + up to N siblings, bounded strip for mid-article junk).
  - `strip_trailing_junk(html)` — removes trailing metadata (wire bylines, editorial credits). Uses lxml. Rules in `_TRAILING_JUNK_RULES` list (10 rules: Got a tip?, BBC trailing email, AP section links, Reporting/Writing/Compiled by, Edited by, Additional reporting by, AP author bio, Image credits, Space.com author bio, Correction).
  - `detect_paywall(html, url)` — detects paywall phrases (subscribe to read, log in to continue, "preview of subscription content", "exclusive to X+ subscribers", etc.) and short-URL truncation indicators (prosyn.org, bit.ly — Project Syndicate pattern)
  - `check_quality(html)` — rejects articles < 200 words post-cleaning (`MIN_CLEAN_WORDS`), and correction-only notices < 100 words
  - `strip_lede_dupe(html)` — removes duplicate lede paragraph that repeats an opening `<em>` block (Reuters mobile API pattern: `<p><em>Summary</em></p> <p><small>By Author</small></p> <p>Summary</p>`). Skips `<p><small>` byline metadata. Also used directly in `_fetch_reuters_feed()`.
  - `strip_figcaption_paragraph_dupe(html)` — removes `<p>` elements that duplicate the preceding `<figcaption>` text (NPR/Space.com pattern). Runs after image processing (which creates `<figure>`/`<figcaption>` tags). Also used in `_fetch_reuters_feed()` and `_fetch_bloomberg_feed()`.
  - Order matters: `strip_junk` → `strip_lede_dupe` → `strip_sciencedaily_metadata` → `strip_bbc_related` → `strip_section_junk` → `strip_trailing_junk` → `detect_paywall` → `check_quality` → (image processing) → `strip_figcaption_paragraph_dupe`
- **Declarative pattern architecture**: Both `feeds.py` and `filters.py` use declarative rule lists for easy extension:
  - `_NORMALIZE_RULES` in `feeds.py` — list of `(pattern, replacement)` tuples for HTML normalization
  - `_JUNK_PATTERN_GROUPS` in `filters.py` — grouped pattern strings compiled into `_JUNK_PATTERNS` regex
  - `_SECTION_JUNK_RULES` in `filters.py` — list of `(heading_pattern, scope)` tuples for structural junk
  - `_TRAILING_JUNK_RULES` in `filters.py` — list of compiled patterns for trailing metadata
- **Stale entry filtering**: `_is_stale_entry()` skips RSS entries older than `_MAX_ENTRY_AGE_DAYS` (7 days) using feedparser's `published_parsed`/`updated_parsed` UTC time tuples. Runs in `_fetch_single_feed()` before extraction — saves time on feeds with chronically stale content (DW 70%, Eater 89%, Morning Brew 45%). Entries with no date are assumed fresh.
- **Image recovery from raw HTML**: `_recover_images_from_html()` recovers images that trafilatura drops during content boundary detection. When extraction produces 0 images, parses the raw HTML for `<img>` tags in content containers (`<article>`, `<main>`, `<figure>`, etc.), filters ads/tracking via `_should_skip_image()`, supports lazy-loading (`data-src`, `data-lazy-src`, `data-original`), resolves relative URLs against the page's base URL, deduplicates, and injects recovered images (no cap — the downstream image pipeline filters junk via size/domain/pattern checks). Hooked into strategies S0b, S1, S1.5, and S2. For S1 (where trafilatura fetches internally), refetches with browser UA only when 0 images detected.
- **Relative URL resolution in image pipeline**: Both `_recover_images_from_html()` and `_process_article_images()` resolve relative image paths (e.g. Al Jazeera's `/wp-content/uploads/...`) against the article's base URL. Without this, trafilatura's `<graphic>` tags with relative `src` attributes would silently fail to download.
- URL filtering: video/podcast/live segments, `.pdf` file extensions, YouTube URLs (`youtube.com`, `youtu.be`), and domain-specific non-article patterns (`_should_skip_url`) are skipped before extraction
- Image dedup: `seen_urls` set in `_process_article_images()` prevents duplicate images within the same article (Verge double-image bug)
- Alt text sanitization: stock photo filenames (`STK071_APPLE_D`, `photo_123.jpg`) are cleared to `alt=""` via `_STOCK_ALT_RE` / `_FILENAME_ALT_RE`
- Image optimization: resize + JPEG compression for e-reader screens
- Google Drive auto-cleanup of old issues (`keep_days` config)
- Google credentials: OAuth tokens from web app DB (CI) or `credentials.json` file (local CLI)
