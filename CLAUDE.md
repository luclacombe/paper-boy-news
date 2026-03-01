# Paper Boy

Automated morning newspaper generator for e-readers (Kobo, Kindle, etc).

## Project Overview

Paper Boy fetches news from RSS feeds, compiles them into a well-formatted EPUB with proper metadata, and delivers it to e-readers via Google Drive (Kobo), email (Kindle Send-to-Kindle), or direct download. Available as both a **CLI tool** and a **Streamlit web app**.

- **CLI**: Build and deliver newspapers from the command line
- **Web App**: Visual interface with onboarding wizard, source management, build dashboard, and edition history
- **GitHub Actions**: Scheduled daily builds (6:00 AM UTC)

## Tech Stack

### Core Library
- **Python 3.9+** with `pyproject.toml` (PEP 621), built with setuptools
- **feedparser** — RSS/Atom feed parsing
- **trafilatura** — Article text extraction from URLs
- **ebooklib** — EPUB creation
- **Pillow** — Cover image generation
- **google-api-python-client + google-auth-oauthlib + google-auth-httplib2** — Google Drive upload
- **click** — CLI framework
- **pyyaml** — Config file parsing

### Web App
- **streamlit** — Web UI framework
- **requests** — GitHub Actions API integration

## Project Structure

```
src/paper_boy/                     # Core library + CLI
├── __init__.py                    # Package init (__version__)
├── cli.py                         # CLI entry point (click commands: build, deliver)
├── config.py                      # YAML config loading + validation (Config, DeliveryConfig, EmailConfig, etc.)
├── feeds.py                       # RSS fetching + article text extraction + image optimization
├── epub.py                        # EPUB generation with metadata + embedded CSS
├── cover.py                       # Cover image generation (600x900px, Pillow)
├── delivery.py                    # Delivery backends: Google Drive, email (Send-to-Kindle), local
└── main.py                        # Orchestration: fetch → build → deliver (returns BuildResult)

web/                               # Streamlit web app
├── app.py                         # Main entry point + page routing
├── requirements.txt               # Web-specific dependencies
├── components/                    # Reusable UI components
│   ├── theme.py                   # CSS design system (newspaper aesthetic)
│   ├── masthead.py                # Newspaper header component
│   ├── navigation.py              # Horizontal nav bar
│   ├── cards.py                   # Status, headline, source, edition cards
│   └── loading.py                 # Empty states + build progress messages
├── pages/                         # Multi-page app
│   ├── landing.py                 # Intro page (pre-onboarding)
│   ├── onboarding.py              # 3-step setup wizard
│   ├── dashboard.py               # "Today's Edition" — build + status
│   ├── sources.py                 # "My Sources" — feed management
│   ├── delivery.py                # "Delivery" — settings
│   └── history.py                 # "Past Editions" — archive
├── services/                      # Backend logic
│   ├── database.py                # User config + history persistence (JSON)
│   ├── builder.py                 # Bridge to paper_boy build pipeline
│   ├── feed_catalog.py            # Curated feed library management
│   └── github_actions.py          # GitHub Actions workflow trigger + status
└── data/
    └── feed_catalog.yaml          # Curated feed catalog (40+ feeds, 7 categories)

.streamlit/
└── config.toml                    # Streamlit theme config (newspaper colors)

tests/
├── test_config.py                 # Config loading + validation tests
├── test_cover.py                  # Cover image generation tests
└── test_epub.py                   # EPUB creation + metadata tests

.github/workflows/
└── daily-news.yml                 # Daily cron (6:00 AM UTC) + manual dispatch
```

## Commands

```bash
# Install core library in development mode
pip install -e ".[dev]"

# Run Streamlit web app
pip install -r web/requirements.txt
streamlit run web/app.py

# CLI: Build newspaper locally
paper-boy build

# CLI: Build and deliver to Google Drive
paper-boy deliver

# CLI: Build with custom config
paper-boy build --config my-config.yaml --output ./output/

# CLI: Verbose logging
paper-boy -v build

# Run tests
pytest
```

## Conventions

- Core library source code lives in `src/paper_boy/`
- Web app source code lives in `web/`
- Web app dependencies are in `web/requirements.txt` (separate from `pyproject.toml`)
- Config is YAML-based (`config.yaml`, see `config.example.yaml`)
- EPUB metadata uses `calibre:series` for Kobo series grouping (Kobo device only)
- EPUB3 standard series metadata included for all devices
- Cover images are 600x900px, generated with Pillow
- Multi-device support: Kobo (Google Drive), Kindle (Send-to-Kindle email), reMarkable (download), Other (download)
- Google Drive delivery targets configurable folder (default "Rakuten Kobo")
- Email delivery uses SMTP (stdlib smtplib) for Send-to-Kindle and generic email
- Google credentials: `GOOGLE_CREDENTIALS` env var (GitHub Actions) or `credentials.json` file (local)
- GitHub Actions secrets store credentials (never commit secrets)
- Tests use pytest, located in `tests/`
- Imports use the `paper_boy` package namespace
- Delivery methods implemented: `google_drive`, `email`, `local`
- `build_newspaper()` returns `BuildResult` (epub_path, sections, total_articles)
- Reset user data: delete `user_config.json` and `delivery_history.json` from project root

## Web App Architecture

### Page Flow
- **Not onboarded**: Landing → Onboarding (3-step wizard) → Dashboard
- **Onboarded**: Dashboard → Sources → Delivery → History (4-page nav)

### Onboarding Steps
1. Choose path (Free Sources vs Paid Subscriptions — only Free enabled)
2. Pick sources (starter bundles, category browsing, or custom RSS)
3. Choose e-reader (Kobo, Kindle, reMarkable, Other) + configure delivery (method, schedule, newspaper settings)

### Services Layer
- `builder.py` bridges web UI config → `paper_boy.Config` → EPUB build + delivery (via `deliver_edition()`)
- `database.py` persists user config + delivery history as JSON files (device, email settings included)
- `feed_catalog.py` loads the curated feed catalog from `web/data/feed_catalog.yaml`
- `github_actions.py` triggers/monitors GitHub Actions builds (wired to dashboard + history pages)

### Design System
- Newspaper aesthetic: Playfair Display + Libre Baskerville (serif), Source Sans 3 (sans)
- Color palette: newsprint (#FAF8F5), ink (#1B1B1B), edition red (#C23B22)
- All CSS is in `web/components/theme.py`

## Key Design Decisions

- **EPUB format** for all e-readers (universal format, supported by Kobo, Kindle, reMarkable, etc.)
- **Multi-device delivery** — Google Drive (Kobo), Send-to-Kindle email, download (all devices)
- **Device-aware EPUB metadata** — calibre:series for Kobo only, standard EPUB3 for all
- **Free RSS sources** for default config (Guardian, Ars Technica, NPR)
- **trafilatura** for full article extraction, with RSS content as fallback
- **Image optimization** in feeds.py — resize + JPEG compression for e-reader
- **Automatic cleanup** of old issues on Google Drive (`keep_days` config)
- **Dashboard delivers end-to-end** — build triggers delivery (Google Drive upload or email) automatically
- **Article headlines** shown on dashboard from build results (stored in session_state)
- **Feed health** tracked from build results — sources page shows active/warning status
- **GitHub Actions integration** — trigger builds from dashboard, view runs in history
- **Streamlit web app** as the primary user-facing interface (CLI remains for automation)
- **Separate dependency specs** — web app has its own `requirements.txt`, core library uses `pyproject.toml`
- **JSON file persistence** for web app state (Phase 1), Supabase planned for Phase 1.5
- **Curated feed catalog** with 40+ feeds across 7 categories and 3 starter bundles
