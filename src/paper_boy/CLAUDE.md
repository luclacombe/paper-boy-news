# src/paper_boy — Core Python Library

The core library that fetches RSS feeds, extracts articles, generates EPUBs, and handles delivery. Used by both the CLI and the FastAPI backend.

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
├── __init__.py       # Package init (__version__)
├── cli.py            # Click CLI entry point (build, deliver commands)
├── config.py         # YAML config loading + validation (Config, DeliveryConfig, EmailConfig)
├── feeds.py          # RSS fetching, article text extraction, image optimization
├── epub.py           # EPUB generation with metadata + embedded CSS
├── cover.py          # Cover image generation (600x900px)
├── delivery.py       # Delivery backends: Google Drive, email (SMTP/Send-to-Kindle), local
└── main.py           # Orchestration: fetch → build → deliver (returns BuildResult)
```

## Key Functions

- `main.build_newspaper(config) → BuildResult` — Main pipeline: fetch feeds → build EPUB → return result
- `main.deliver_newspaper(config, epub_path)` — Deliver EPUB via configured method
- `feeds.fetch_feeds(config) → list[Section]` — Fetch all configured feeds, extract articles
- `epub.create_epub(sections, config) → path` — Generate EPUB file
- `cover.create_cover(title, date) → bytes` — Generate cover image
- `delivery.deliver_to_google_drive(path, config)` — Upload to Google Drive
- `delivery.deliver_via_email(path, config)` — Send via SMTP

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

## Design Decisions

- EPUB3 format for universal e-reader support
- `calibre:series` metadata for Kobo series grouping, standard EPUB3 series for all devices
- trafilatura for full article extraction with RSS content as fallback
- Image optimization: resize + JPEG compression for e-reader screens
- Google Drive auto-cleanup of old issues (`keep_days` config)
- Google credentials: `GOOGLE_CREDENTIALS` env var (CI) or `credentials.json` file (local)
