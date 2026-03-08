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

## Install

```bash
pip install -e ".[dev]"    # Editable install with dev deps (pytest, httpx)
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
├── config.py         # YAML config loading + validation (Config, DeliveryConfig, EmailConfig)
├── feeds.py          # RSS fetching, article text extraction, image optimization
├── epub.py           # EPUB generation with metadata + embedded CSS
├── cover.py          # Cover image generation (600x900px)
├── delivery.py       # Delivery backends: Google Drive, email (SMTP/Send-to-Kindle), local
└── main.py           # Orchestration: fetch → build → deliver (returns BuildResult)
```

## Key Functions

- `main.build_newspaper(config, cache=None) → BuildResult` — Main pipeline: fetch feeds → build EPUB → return result
- `main.build_and_deliver(config, cache=None) → BuildResult` — Build + deliver EPUB
- `feeds.fetch_feeds(config, cache=None) → list[Section]` — Fetch all configured feeds, extract articles
- `cache.ContentCache` — In-memory cache for feed entries, article HTML, and image bytes
- `epub.build_epub(sections, config) → path` — Generate EPUB file
- `cover.generate_cover(title, sections, issue_date) → bytes` — Generate newspaper-style cover image (600x900 JPEG)
- `delivery.deliver(path, config)` — Deliver via configured method (Google Drive, email, local)

## Config Format

YAML-based (`config.yaml`), see `config.example.yaml` in project root:

```yaml
title: "Morning Digest"
language: en
max_articles_per_feed: 10
include_images: true
feeds:
  - name: "The Guardian"
    url: "https://www.theguardian.com/world/rss"
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

- In-memory only, scoped to a single `run_scheduled()` invocation
- All functions accept an optional `cache` param (default `None`) — backward compatible
- Article key includes `include_images` because trafilatura output differs based on this flag
- Image cache stores raw bytes (pre-optimization) since optimization settings may vary per user
- Failed extractions/downloads are cached as `None` to prevent retries
- `cache.log_stats()` logs hit/miss summary after each scheduled run

## Design Decisions

- **Bundled font**: Playfair Display (OFL-licensed variable TTF) in `src/paper_boy/fonts/`. Supports Regular through Black weights via `set_variation_by_name()`. Guarantees consistent cover rendering on all platforms including CI (no bitmap fallback). ~300KB, included as package data in `pyproject.toml`.
- **Cover layout**: Newspaper broadsheet style — double-rule masthead with auto-scaling title, red-accented lead headline, secondary headlines grouped by section with thin rules. Masthead font scales down automatically for long titles.
- **EPUB CSS**: Optimized for e-ink displays — paragraph indent (except first), justified text, larger body font (1.05em), improved line-height (1.7). Avoids CSS Grid/Flexbox (unsupported on most e-readers).
- EPUB3 format for universal e-reader support
- `calibre:series` metadata for Kobo series grouping, standard EPUB3 series for all devices
- Multi-strategy article extraction with fallback chain (`_extract_article_content`):
  1. Standard trafilatura (default UA)
  2. Re-fetch with bot UA (`archive.org_bot`) → trafilatura
  3. JSON-LD structured data extraction (`articleBody` / `text` fields)
  - `MIN_ARTICLE_WORDS = 150` threshold to detect truncated/paywalled content
  - All paths normalised via `_normalize_html()` (strips empty tags, inline styles, NPR caption artifacts)
  - Falls back to RSS feed content if all strategies fail
- `_convert_graphics_to_imgs()` normalises TEI XML `<graphic>` tags to `<img>` before the image pipeline runs (trafilatura emits `<graphic>` instead of `<img>` with `output_format="html"`)
- `_strip_duplicate_title()` removes leading `<h1>`/`<h2>` from extracted HTML when it matches the article title (fuzzy: case-insensitive, punctuation-stripped, containment check) — prevents double headings since `epub.py` adds its own `<h1>` from `Article.title`
- Video/podcast/live URL segments are filtered out before extraction (Al Jazeera `/video/` etc.)
- Image optimization: resize + JPEG compression for e-reader screens
- Google Drive auto-cleanup of old issues (`keep_days` config)
- Google credentials: OAuth tokens from web app DB (CI) or `credentials.json` file (local CLI)
