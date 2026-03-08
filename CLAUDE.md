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

"Get it now" flow:
1. Next.js server action creates `delivery_history` record with `status: "building"`
2. Fires `repository_dispatch` to GitHub Actions with `{ record_id }` (no PII)
3. Returns immediately — dashboard polls Supabase every 5s for completion
4. GitHub Actions runs `scripts/build_for_users.py` which builds EPUB, delivers, and updates the DB record
5. Dashboard detects `status: "delivered"` or `status: "failed"` and transitions state

Scheduled delivery:
- GitHub Actions cron runs every 30 min
- `build_for_users.py` scans all onboarded users, builds for those within ±15 min of their delivery window
- A shared `ContentCache` deduplicates RSS fetches, article extraction, and image downloads across users within the same scheduled run

## Project Structure

```
src/paper_boy/           # Core Python library + CLI (see src/paper_boy/CLAUDE.md)
  cache.py               # In-memory content cache (feeds, articles, images)
web/                     # Next.js web app (see web/CLAUDE.md)
scripts/                 # Build script for GitHub Actions
legacy/streamlit/        # Archived Streamlit prototype
legacy/api/              # Archived FastAPI backend (replaced by GitHub Actions)
tests/                   # Python tests for core lib
.github/workflows/       # CI + build-newspaper
```

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
- Cover images: 600x900px, generated with Pillow
- Secrets: never commit `.env.local`, use env vars in CI/deployment

## Deployment

| Service | Platform | Config |
|---------|----------|--------|
| Web app | Vercel | `web/` directory, `paper-boy-news.vercel.app` |
| EPUB builds | GitHub Actions | `.github/workflows/build-newspaper.yml` |
| Database | Supabase | PostgreSQL + Auth + Storage |

## Edition Model

Editions use a **5 AM rollover** in the user's configured timezone (not UTC midnight):

- Before 5 AM user-local → current edition is **yesterday's**
- After 5 AM → current edition is **today's**
- One edition per calendar day per user (enforced by partial unique index on `delivery_history`)
- Delivery time (5–8 AM) = when the paper gets pushed to the user's device
- "Get it now" = async build via GitHub Actions (dashboard polls for completion)

Key files:
- `web/src/lib/edition-date.ts` — timezone-aware edition date calculation
- `web/src/actions/build.ts` — `getItNow()` action with dedup guard + GitHub dispatch
- `web/src/components/dashboard-client.tsx` — 8-state dashboard state machine with polling
- `scripts/build_for_users.py` — build runner for GitHub Actions

## Current Status

- Core library, auth, and server actions are complete
- Dashboard (`/dashboard`) — 8-state status card, async build with polling, past editions, schedule nudges, "Send to device" via File System Access API (Chrome/Edge)
- Settings (`/settings`) — accordion with 4 colored-border cards, batch save with undo toast (3s countdown + halftone texture), catalog-based source management, per-page header with sign out. Deep linking from dashboard via `?open=`
- Feed validation and SMTP test run as Next.js API routes (no external backend needed)
- Old routes (`/sources`, `/delivery`, `/editions`) redirect to `/settings` or `/dashboard`
- Onboarding wizard and login flow are functional
- Legacy Streamlit prototype archived in `legacy/streamlit/`
- Legacy FastAPI backend archived in `legacy/api/`
