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
- `cover.generate_cover(sections, config) → bytes` — Generate cover image
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

- EPUB3 format for universal e-reader support
- `calibre:series` metadata for Kobo series grouping, standard EPUB3 series for all devices
- trafilatura for full article extraction with RSS content as fallback
- Image optimization: resize + JPEG compression for e-reader screens
- Google Drive auto-cleanup of old issues (`keep_days` config)
- Google credentials: OAuth tokens from web app DB (CI) or `credentials.json` file (local CLI)
