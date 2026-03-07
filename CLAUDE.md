# Paper Boy

Automated morning newspaper generator for e-readers (Kobo, Kindle, reMarkable).

## Project Overview

Paper Boy fetches news from RSS feeds, compiles them into a well-formatted EPUB, and delivers it to e-readers via Google Drive (Kobo), email (Kindle Send-to-Kindle), or direct download.

The project has three components:

1. **Core Python library** (`src/paper_boy/`) — RSS fetching, EPUB generation, delivery backends, CLI
2. **FastAPI backend** (`api/`) — HTTP API wrapping the core library, deployed on Railway
3. **Next.js web app** (`web-next/`) — Full-stack web UI with Supabase auth, deployed on Vercel

There is also a legacy **Streamlit app** (`web/`) that is being replaced by the Next.js app and will be removed soon.

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Next.js (Vercel)  │────▶│  FastAPI (Railway)   │────▶│  Core Python lib    │
│   web-next/         │     │  api/                │     │  src/paper_boy/     │
│                     │     │                      │     │                     │
│  Supabase Auth      │     │  POST /build         │     │  feedparser         │
│  Drizzle ORM        │     │  POST /deliver       │     │  trafilatura        │
│  Server Actions     │     │  POST /feeds/validate│     │  ebooklib           │
│  App Router         │     │  POST /smtp-test     │     │  Pillow (covers)    │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
         │                                                        │
         ▼                                                        ▼
┌─────────────────────┐                               ┌─────────────────────┐
│  Supabase           │                               │  CLI (paper-boy)    │
│  PostgreSQL + Auth  │                               │  GitHub Actions     │
│  Storage (EPUBs)    │                               │  Daily cron builds  │
└─────────────────────┘                               └─────────────────────┘
```

## Project Structure

```
src/paper_boy/           # Core Python library + CLI (see src/paper_boy/CLAUDE.md)
api/                     # FastAPI backend (see api/CLAUDE.md)
web-next/                # Next.js web app (see web-next/CLAUDE.md)
web/                     # Legacy Streamlit app (being replaced — do not extend)
tests/                   # Python tests for core lib + API (see tests/CLAUDE.md)
.github/workflows/       # CI + daily cron
```

## Tech Stack

| Component | Stack |
|-----------|-------|
| Core library | Python 3.9+, feedparser, trafilatura, ebooklib, Pillow, click |
| API | FastAPI, uvicorn, deployed on Railway (Docker) |
| Web app | Next.js 16, React 19, TypeScript (strict), Tailwind CSS v4, shadcn/ui |
| Auth | Supabase Auth (Google OAuth + email/password) |
| Database | Supabase PostgreSQL via Drizzle ORM |
| Package manager | pnpm (web-next), pip (Python) |
| Testing | Vitest (web-next), pytest (Python) |
| CI | GitHub Actions — Python tests + Next.js lint/test/build |

## Commands

```bash
# ── Core library ──
pip install -e ".[dev]"           # Install in dev mode
paper-boy build                   # CLI: build newspaper
paper-boy deliver                 # CLI: build + deliver
pytest                            # Run Python tests

# ── FastAPI backend ──
pip install -r api/requirements.txt
uvicorn api.main:app --reload     # Run API locally (port 8000)

# ── Next.js web app ──
cd web-next
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

# ── Dev helpers (from web-next/) ──
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
   cd web-next
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
- Server Actions in `web-next/src/actions/` for all data mutations
- Drizzle ORM for database access (never raw SQL in app code)
- Supabase client via `@/lib/supabase/server.ts` (server) and `@/lib/supabase/client.ts` (browser)
- All types in `web-next/src/types/index.ts`
- Core Python library uses `paper_boy` package namespace
- Config is YAML-based for CLI (`config.yaml`), Supabase DB for web app
- EPUB metadata: `calibre:series` for Kobo, standard EPUB3 for all devices
- Cover images: 600x900px, generated with Pillow
- Secrets: never commit `.env.local`, use env vars in CI/deployment

## Deployment

| Service | Platform | Config |
|---------|----------|--------|
| Web app | Vercel | `web-next/` directory, `paper-boy-news.vercel.app` |
| API | Railway | `api/Dockerfile`, `railway.toml` |
| Database | Supabase | PostgreSQL + Auth + Storage |
| Daily builds | GitHub Actions | `.github/workflows/daily-news.yml` (6:00 AM UTC) |

## Edition Model

Editions use a **5 AM rollover** in the user's configured timezone (not UTC midnight):

- Before 5 AM user-local → current edition is **yesterday's**
- After 5 AM → current edition is **today's**
- One edition per calendar day per user (enforced by partial unique index on `delivery_history`)
- Delivery time (5–8 AM) = when the paper gets pushed to the user's device
- "Get it now" = build + deliver on demand (only available after 5 AM)

Key files:
- `web-next/src/lib/edition-date.ts` — timezone-aware edition date calculation
- `web-next/src/actions/build.ts` — `getItNow()` action with dedup guard
- `web-next/src/components/dashboard-client.tsx` — 8-state dashboard state machine

**Scheduled delivery (cron)** is designed but not yet implemented — see plan at `.claude/plans/replicated-wobbling-harp.md`.

## Current Status

- Core library, API, auth, and server actions are complete
- Dashboard (`/dashboard`) — 8-state status card, build controls, past editions, schedule nudges
- Settings (`/settings`) — accordion with 4 colored-border cards, batch save with undo toast (3s countdown + halftone texture), catalog-based source management, per-page header with sign out. Deep linking from dashboard via `?open=`
- Old routes (`/sources`, `/delivery`, `/editions`) redirect to `/settings` or `/dashboard`
- Onboarding wizard and login flow are functional
- Legacy Streamlit app (`web/`) still present, pending removal
