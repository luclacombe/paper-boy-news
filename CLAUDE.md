# Paper Boy

Automated morning newspaper generator for e-readers (Kobo, Kindle, reMarkable).

## Project Overview

Paper Boy fetches news from RSS feeds, compiles them into a well-formatted EPUB, and delivers it to e-readers via Google Drive (Kobo), email (Kindle Send-to-Kindle), or direct download.

The project has two main components:

1. **Core Python library** (`src/paper_boy/`) — RSS fetching, EPUB generation, delivery backends, CLI
2. **Next.js web app** (`web/`) — Full-stack web UI with Supabase auth, deployed on Vercel

EPUB builds run in **GitHub Actions** via `repository_dispatch` (on-demand) and cron (scheduled delivery).

Legacy code is archived in `legacy/` (Streamlit prototype and former FastAPI backend).

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Next.js (Vercel)  │     │  GitHub Actions      │     │  Core Python lib    │
│   web/              │     │  .github/workflows/  │     │  src/paper_boy/     │
│                     │     │                      │     │                     │
│  Supabase Auth      │     │  repository_dispatch │     │  feedparser         │
│  Drizzle ORM        │────▶│  (on-demand builds)  │────▶│  trafilatura        │
│  Server Actions     │     │                      │     │  ebooklib           │
│  API Routes         │     │  cron (scheduled)    │     │  Pillow (covers)    │
│  App Router         │     │                      │     │                     │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
         │                           │                            │
         ▼                           ▼                            ▼
┌─────────────────────┐     ┌─────────────────────┐   ┌─────────────────────┐
│  Supabase           │     │  scripts/            │   │  CLI (paper-boy)    │
│  PostgreSQL + Auth  │◀────│  build_for_users.py  │   │  Local dev/testing  │
│  Storage (EPUBs)    │     │  (reads/writes DB)   │   │                     │
└─────────────────────┘     └─────────────────────┘   └─────────────────────┘
```

## Build Pipeline

Two-phase scheduled pipeline (6 build windows + delivery checks):

**Build phase** (6 windows every 4 hours at :45 — 03:45, 07:45, 11:45, 15:45, 19:45, 23:45 UTC):
1. GitHub Actions cron triggers `BUILD_MODE=build`
2. Pre-check queries Supabase for user timezones; skips Python setup if no users are in midnight–5 AM window
3. `build_for_users.py` builds only users whose local time is midnight–5 AM (others caught by next window)
4. Shared `ContentCache` deduplicates RSS fetches, article extraction, and image downloads across users in the window
5. EPUBs uploaded to Supabase Storage; records set to `status: "built"` (or `"delivered"` for local/download users)

**Deliver phase** (every 30 min at :00/:30):
1. GitHub Actions cron triggers `BUILD_MODE=deliver`
2. `build_for_users.py` scans for `status: "built"` records within ±15 min of each user's delivery window
3. Downloads EPUB from Storage, delivers via Google Drive/email/Gmail, updates to `status: "delivered"`

**"Get it now" flow** (on-demand):
1. Next.js server action creates `delivery_history` record with `status: "building"` + snapshots `delivery_method`
2. If a `"built"` record already exists, dispatches delivery-only instead of rebuilding
3. Fires `repository_dispatch` to GitHub Actions with `{ record_id }` (no PII)
4. Returns immediately — dashboard polls Supabase every 5s for completion
5. Dashboard detects `status: "delivered"`, `"built"`, or `"failed"` and transitions state
6. Settings locks Sources/Delivery/Schedule sections during active builds to prevent mid-build changes

**Status lifecycle:** `building → built → delivered` (or `→ failed` at any step)

## Project Structure

```
src/paper_boy/           # Core Python library + CLI (see src/paper_boy/CLAUDE.md)
  cache.py               # In-memory content cache (feeds, articles, images)
  filters.py             # Post-extraction content filters (paywall, junk, quality)
web/                     # Next.js web app (see web/CLAUDE.md)
  src/app/api/opds/      # OPDS feed + EPUB download proxy (token-based auth)
scripts/                 # Build script for GitHub Actions
legacy/streamlit/        # Archived Streamlit prototype
legacy/api/              # Archived FastAPI backend (replaced by GitHub Actions)
tests/                   # Python tests for core lib
.github/workflows/       # CI + build-newspaper
```

## Source Audit Workflow

Two-skill workflow for auditing EPUB output quality across all sources:

1. **`/build-audit`** — runs a full `--no-limit` build, extracts the EPUB, updates `BUILD-INFO.md` with per-source stats (article counts, timing, strategies, failures)
2. **`/source-audit [Category]`** — deep quality audit of one category at a time against the extracted EPUB

**Source audit process** (5 phases per category):
1. Bootstrap — reads `SOURCE-AUDIT-DISCOVERIES.md` (check library) + `SOURCE-AUDIT-ISSUES.md` (tracker) + `BUILD-INFO.md`
2. Automated sweep — Python script checks all articles for 11+ patterns (title dup, junk, figcaption quality, word count outliers, etc.)
3. Build log analysis — strategy efficiency, timing, failure patterns per source
4. RSS feed analysis — live fetch to check category metadata, date formats, content richness
5. Deep read — 3 sampled articles per source, exploratory checks, cross-article comparison

**Key files** (all in `audit/`, gitignored — local working files):
- `audit/SOURCE-AUDIT-DISCOVERIES.md` — growing library of "what to check for" (DISC-* IDs)
- `audit/SOURCE-AUDIT-ISSUES.md` — issue tracker with cross-source (XSRC-*) and per-source (SRC-*) issues + audit progress table
- `audit/BUILD-INFO.md` — latest build stats baseline
- `audit/STRATEGY-MAP.md` — per-source optimal extraction strategy profiles
- `audit/build-audit.log` — verbose build output for log analysis

Run one category per session. Findings persist across sessions via the two tracker files.

## Tech Stack

| Component | Stack |
|-----------|-------|
| Core library | Python 3.9+, feedparser, trafilatura, ebooklib, Pillow, click |
| Build runner | GitHub Actions, `scripts/build_for_users.py`, Supabase Python client |
| Web app | Next.js 16, React 19, TypeScript (strict), Tailwind CSS v4, shadcn/ui |
| Auth | Supabase Auth (Google OAuth + email/password) |
| Database | Supabase PostgreSQL via Drizzle ORM |
| Package manager | pnpm (web), pip (Python) |
| Testing | Vitest (web), pytest (Python) |
| CI | GitHub Actions — Python tests + Next.js lint/test/build |

## Commands

```bash
# ── Core library ──
pip install -e ".[dev]"           # Install in dev mode
paper-boy build                   # CLI: build newspaper
paper-boy deliver                 # CLI: build + deliver
pytest                            # Run Python tests

# ── Next.js web app ──
cd web
pnpm install                      # Install dependencies
pnpm dev                          # Dev server (port 3000)
pnpm build                        # Production build
pnpm lint                         # ESLint
pnpm test                         # Vitest
pnpm db:push                      # Push Drizzle schema to DB
pnpm db:studio                    # Open Drizzle Studio

# ── Local Supabase (Docker required) ──
supabase start                    # Start local Postgres + Auth + Studio + Inbucket
supabase stop                     # Stop local Supabase
supabase db reset                 # Reset DB, re-run migrations + seed data

# ── Dev helpers (from web/) ──
pnpm env:local                    # Switch to local Supabase
pnpm env:cloud                    # Switch to cloud Supabase
pnpm dev:reset                    # Reset all users to pre-onboarding state (DB only)
pnpm dev:reset -- --email X       # Reset specific user by email
# After dev:reset, visit /dev/reset in browser to clear localStorage + sign out
```

## Local Development (Supabase)

For testing auth flows (onboarding, sign-up, login, delivery) without touching production:

1. **Prerequisites**: Docker Desktop running, Supabase CLI installed
2. **First-time setup**:
   ```bash
   supabase start                                  # From project root — starts all services
   cd web
   cp .env.local .env.local.cloud                  # Save cloud credentials
   cp .env.local.example .env.local.dev            # Local credentials template (pre-filled)
   pnpm env:local                                  # Activate local env
   pnpm install                                    # Install deps (adds tsx)
   pnpm dev                                        # Start Next.js
   ```
3. **Seeded test accounts** (password: `password123`):
   - `dev@paperboy.local` — fresh user, onboarding not complete
   - `onboarded@paperboy.local` — onboarded with feeds + delivery history
4. **Re-test onboarding**: `pnpm dev:reset` then visit `/dev/reset` in browser (clears localStorage + signs out)
5. **Full DB reset**: `supabase db reset` — drops everything, re-runs migrations + seed

**Local services**:
| Service | URL |
|---------|-----|
| Studio (DB browser) | http://localhost:54323 |
| Inbucket (email catcher) | http://localhost:54324 |
| Auth API | http://localhost:54321/auth/v1 |
| REST API | http://localhost:54321/rest/v1 |

**Note**: Google OAuth sign-in doesn't work locally — use email/password instead (no email confirmation required). Google Drive/Gmail delivery testing still requires real OAuth tokens.

## Documentation Rules

When making code changes, keep documentation in sync automatically — no user reminder needed:
- **Update** the relevant CLAUDE.md file(s) when changes affect documented architecture, features, conventions, or status
- **Remove** documented items that no longer exist (deleted features, renamed files, removed modules)
- **Add** documentation for new features, modules, or patterns that are on par with what's already documented
- **Create** a new CLAUDE.md if a new significant subdirectory emerges that warrants its own docs
- **Delete** a CLAUDE.md if its directory is removed or archived

Each subdirectory has its own CLAUDE.md:
- `CLAUDE.md` (root) — architecture, build pipeline, edition model, current status
- `src/paper_boy/CLAUDE.md` — Python library modules, config format, design decisions
- `web/CLAUDE.md` — web app structure, DB schema, auth, key patterns
- `tests/CLAUDE.md` — test organization, run commands, conventions

Do NOT write implementation details to auto-memory (`MEMORY.md`). Memory is only for behavioral rules and cross-session gotchas not covered in any CLAUDE.md.

## Conventions

- TypeScript strict mode, path alias `@/*` → `src/*`
- Tailwind CSS v4 + shadcn/ui for all styling
- Server Actions in `web/src/actions/` for all data mutations
- Drizzle ORM for database access (never raw SQL in app code)
- Supabase client via `@/lib/supabase/server.ts` (server) and `@/lib/supabase/client.ts` (browser)
- All types in `web/src/types/index.ts`
- Core Python library uses `paper_boy` package namespace
- Config is YAML-based for CLI (`config.yaml`), Supabase DB for web app
- EPUB metadata: `calibre:series` for Kobo, standard EPUB3 for all devices
- EPUB structure: category-grouped when feeds have categories (web app), flat when no categories (CLI). Cover page first in spine with EPUB3 landmarks nav + EPUB2 guide for proper opening behavior
- Post-extraction content filtering pipeline: junk stripping → paywall detection → quality gate (see `filters.py`)
- Cover images: 600x900px, generated with Pillow, category-aware labels
- Secrets: never commit `.env.local`, use env vars in CI/deployment

## Deployment

| Service | Platform | Config |
|---------|----------|--------|
| Web app | Vercel | `web/` directory, `www.paper-boy-news.com` |
| EPUB builds | GitHub Actions | `.github/workflows/build-newspaper.yml` |
| Database | Supabase | PostgreSQL + Auth + Storage |

## Edition Model

Edition date = **today's calendar date** in the user's configured timezone (no rollover):

- Edition date is always today's date — `getEditionDate()` returns the current calendar date
- One edition per calendar day per user (enforced by partial unique index on `delivery_history`)
- Build time = midnight–5 AM user-local (6 build windows every 4 hours cover all timezones)
- Delivery time (5–8 AM user-local) = when the paper gets pushed to the user's device
- "Get it now" = async build (or delivery-only if already built) via GitHub Actions
- `isBeforeEditionCutoff()` checks if before 5 AM local — used for UI messaging (paper may still be building)

Key files:
- `web/src/lib/edition-date.ts` — timezone-aware edition date calculation
- `web/src/actions/build.ts` — `getItNow()` action with dedup guard + GitHub dispatch
- `web/src/components/dashboard-client.tsx` — 9-state dashboard state machine with polling
- `scripts/build_for_users.py` — build runner for GitHub Actions (3 modes: build, deliver, on-demand)

## Current Status

- Core library, auth, and server actions are complete
- Dashboard (`/dashboard`) — 9-state status card (including `awaiting-delivery`), async build with polling, past editions, schedule nudges, "Send to device" via File System Access API (Chrome/Edge). Build-in-progress state takes priority over setup-incomplete (safe when settings change mid-build)
- Settings (`/settings`) — accordion with 5 colored-border cards (Sources, Delivery, Schedule, Paper, Account), batch save with undo toast (3s countdown + halftone texture), catalog-based source management, per-page header with sign out. Deep linking from dashboard via `?open=`. Sources/Delivery/Schedule locked during active builds. Account section: email display, password change (email users), account deletion with confirmation
- OPDS wireless sync — per-user token-authenticated OPDS feed (`/api/opds/[token]/feed.xml`) + EPUB download proxy (`/api/opds/[token]/download/[editionId]`). Pull-based, no build pipeline changes. Enables KOReader on any Kobo, reMarkable, PocketBook, or jailbroken Kindle to auto-download daily editions. Toggle in Delivery settings (immediate action, not batch-saved)
- Feed validation and SMTP test run as Next.js API routes (no external backend needed)
- Old routes (`/sources`, `/delivery`, `/editions`) redirect to `/settings` or `/dashboard`
- Onboarding wizard and login flow are functional
- Legacy Streamlit prototype archived in `legacy/streamlit/`
- Legacy FastAPI backend archived in `legacy/api/`
