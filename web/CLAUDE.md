# web — Next.js Web App

Full-stack web app for Paper Boy. Deployed on Vercel at `paper-boy-news.vercel.app`.

## Stack

- **Next.js 16** (App Router), **React 19**, **TypeScript** (strict)
- **Tailwind CSS v4** + **shadcn/ui** (Radix primitives)
- **Supabase** — Auth (Google OAuth + email/password), PostgreSQL, Storage
- **Drizzle ORM** — schema in `src/db/schema.ts`, migrations in `src/db/migrations/`
- **pnpm** package manager
- **Vitest** for testing

## Commands

```bash
pnpm dev              # Dev server (port 3000)
pnpm build            # Production build
pnpm lint             # ESLint
pnpm test             # Vitest
pnpm db:push          # Push Drizzle schema to Supabase
pnpm db:studio        # Drizzle Studio (DB browser)

# Dev helpers
pnpm env:local        # Switch .env.local to local Supabase
pnpm env:cloud        # Switch .env.local to cloud Supabase
pnpm dev:reset        # Reset all users to pre-onboarding state (DB only)
pnpm dev:reset -- --email dev@paperboy.local  # Reset specific user
pnpm dev:reset -- --onboarding   # Only reset onboarding flag
pnpm dev:reset -- --history      # Only clear delivery history
pnpm dev:reset -- --feeds        # Only clear feeds
# After dev:reset, visit /dev/reset in browser to clear localStorage + sign out
pnpm supabase:start   # Start local Supabase (Docker required)
pnpm supabase:stop    # Stop local Supabase
pnpm supabase:reset   # Full DB reset (migrations + seed)
```

## Directory Structure

```
src/
├── actions/           # Server Actions (all data mutations)
│   ├── build.ts       # getItNow() — timezone-aware build + deliver with dedup guard
│   ├── delivery-history.ts
│   ├── feed-catalog.ts
│   ├── feeds.ts       # CRUD for user_feeds table
│   ├── google-oauth.ts
│   ├── onboarding.ts  # completeOnboarding() — saves wizard state to DB
│   └── user-config.ts
├── app/
│   ├── globals.css    # Tailwind v4 config + newspaper palette + shadcn tokens
│   ├── layout.tsx     # Root layout (fonts, Toaster)
│   ├── (marketing)/   # Public landing page
│   ├── (auth)/        # Login/signup (Google OAuth + email/password)
│   ├── onboarding/    # 4-step wizard + /onboarding/complete (post-OAuth)
│   ├── (app)/         # Protected routes (requires auth + onboarding)
│   │   ├── layout.tsx # Auth check, redirects if not onboarded (no masthead — per-page headers)
│   │   ├── dashboard/ # Newspaper front page — status hub, build, back issues
│   │   └── settings/  # Accordion settings (?open= deep linking from dashboard)
│   └── api/
│       ├── auth/      # OAuth callback routes (Supabase + Google)
│       ├── feeds/validate/ # RSS feed URL validation (replaces FastAPI)
│       └── smtp-test/ # SMTP connection test (replaces FastAPI)
├── components/
│   ├── ui/            # shadcn/ui primitives (button, card, input, etc.)
│   ├── settings/      # Settings section panels (sources, delivery, schedule, paper)
│   ├── app-masthead.tsx      # Newspaper masthead (rendered by dashboard page, not layout)
│   ├── dashboard-client.tsx  # Dashboard interactive UI (deep links to settings via ?open=)
│   ├── save-toast.tsx         # Custom save toast: halftone texture, countdown progress bar, undo
│   ├── settings-accordion.tsx # Accordion cards with colored borders, batch save + undo
│   ├── settings-client.tsx   # Settings page: compact header (← Settings / Sign out) + accordion
│   └── *.tsx          # Shared components (device-card, edition-card, etc.)
├── data/
│   └── feed-catalog.yaml  # Curated feed catalog (40+ feeds, 7 categories)
├── db/
│   ├── index.ts       # Drizzle client (postgres-js driver)
│   ├── schema.ts      # 3 tables: user_profiles, user_feeds, delivery_history
│   └── migrations/    # SQL migrations (RLS policies, triggers)
├── hooks/
│   └── use-onboarding-state.ts  # localStorage persistence for wizard
├── lib/
│   ├── github-dispatch.ts # GitHub Actions repository_dispatch for builds
│   ├── auth.ts        # getAuthUser(), getUserProfile()
│   ├── setup-status.ts # Compute delivery setup completeness
│   ├── download-epub.ts # Browser-side EPUB download from Supabase Storage
│   ├── constants.ts   # DEVICES, TIMEZONES, DELIVERY_TIMES, EDITION_ROLLOVER_HOUR, BUILD_MESSAGES
│   ├── edition-date.ts # Timezone-aware edition date (5 AM rollover), cutoff checks
│   ├── feed-catalog.ts
│   ├── reading-time.ts
│   ├── utils.ts       # cn() helper (clsx + tailwind-merge)
│   └── supabase/
│       ├── client.ts  # Browser Supabase client
│       └── server.ts  # Server Supabase client (for Server Components + Actions)
├── proxy.ts           # Auth routing (protect app routes, redirect auth users)
├── types/
│   └── index.ts       # All TypeScript types
└── __tests__/
    ├── setup.ts       # Global test setup (vi.mock for next/headers)
    ├── actions/       # Unit tests for server actions
    └── e2e/           # Integration tests
```

## Database Schema (Drizzle)

3 tables, all with RLS policies:

- **user_profiles** — extends Supabase auth.users (newspaper settings, device, delivery config, Google tokens, onboarding state)
- **user_feeds** — user's RSS feeds (name, url, category, position), FK → user_profiles
- **delivery_history** — build/delivery records (status, article count, sections JSON, EPUB storage path), FK → user_profiles

Auto-triggers: `on_auth_user_created` → creates profile row, `updated_at` auto-update.

Partial unique index: `idx_delivery_unique_edition` on `(user_id, edition_date) WHERE status != 'failed'` — enforces one non-failed edition per user per day, allows retries after failures.

## Auth Flow

1. User signs up via Google OAuth or email/password (Supabase Auth)
2. Onboarding wizard saves state to localStorage (no auth required for `/onboarding`)
3. Google OAuth redirect → `/onboarding/complete` saves localStorage state to DB
4. Proxy protects `/dashboard`, `/settings` (and legacy `/sources`, `/delivery`, `/editions`) — requires auth
5. Google Drive/Gmail OAuth is **separate** from sign-in OAuth (scopes: drive.file, gmail.send)

## Key Patterns

- **Server Actions** (`src/actions/`) for all mutations — each gets auth user, queries/mutates via Drizzle
- **Path alias** `@/*` maps to `src/*`
- **Types** centralized in `src/types/index.ts`
- **Supabase clients**: use `server.ts` in Server Components/Actions, `client.ts` in Client Components
- **Feed validation + SMTP test** run as Next.js API routes (`/api/feeds/validate`, `/api/smtp-test`)
- **Edition model**: editions roll over at 5 AM user-local (not midnight UTC). One per day, enforced by partial unique DB index. See `src/lib/edition-date.ts`
- **Build pipeline**: `getItNow()` action → checks dedup → creates "building" record → fires GitHub Actions `repository_dispatch` → returns immediately. Dashboard polls Supabase every 5s. GitHub Actions runs `scripts/build_for_users.py` which builds EPUB, delivers, and updates the DB record
- **Dashboard state machine**: 8 states computed from edition status, time of day, and setup completeness. Pure function `getDashboardState()` exported from `dashboard-client.tsx` for testability
- **Settings accordion**: 4 collapsible cards with colored left borders (red/ink/amber/green). One open at a time. Deep linking via `?open=sources|delivery|schedule|paper`. All sections use batch save — "Save changes" when dirty, auto-save on collapse. Custom save toast (`save-toast.tsx`) with halftone texture, 3s countdown progress bar, and undo. Sources undo uses `setFeeds()` bulk replace; config undo restores previous snapshot. Summary generators exported from `settings-accordion.tsx` for testing
- **Per-page headers**: AppMasthead is rendered by dashboard (not shared layout). Settings has its own compact header with back link + sign out

## Design System

- Newspaper aesthetic: Playfair Display (headings), Libre Baskerville (body), Source Sans 3 (UI), JetBrains Mono (code)
- Color palette defined in `globals.css`: newsprint (#FAF8F5), ink (#1B1B1B), edition red, delivered green, building amber
- Lucide icons via `lucide-react`
- shadcn/ui components in `src/components/ui/`

## Environment Variables

See `.env.example` for cloud vars, `.env.local.example` for local Supabase:
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL` (Supabase PostgreSQL connection string)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (for Drive/Gmail OAuth)
- `NEXT_PUBLIC_APP_URL` (for OAuth redirects)
- `GITHUB_PAT`, `GITHUB_REPO` (server-side only, for build dispatch)

**Env file strategy**:
- `.env.local` — active env (used by Next.js, gitignored)
- `.env.local.dev` — local Supabase credentials (gitignored)
- `.env.local.cloud` — cloud Supabase credentials (gitignored)
- `.env.local.example` — local Supabase template with default keys (committed)
- `.env.example` — cloud env template (committed)

## Edition Model

Editions use a **5 AM rollover** in the user's configured timezone:
- Before 5 AM → current edition = yesterday. After 5 AM → current edition = today.
- `getEditionDate(timezone)` in `src/lib/edition-date.ts` is the single source of truth.
- `getItNow()` in `src/actions/build.ts` checks for existing editions before building (dedup guard), then dispatches async build to GitHub Actions.

Dashboard states (in priority order): setup-incomplete → build-in-progress (client or DB "building") → build-error → fetched-early → delivered → failed → pre-build-first / pre-build → ready-first / ready.

**Scheduled delivery**: GitHub Actions cron runs every 30 min, `scripts/build_for_users.py` scans users and builds within ±15 min of their delivery window.

## Current Status

- Auth, onboarding, and server actions are complete
- Dashboard (`/dashboard`) — 8-state status card with timezone-aware edition logic, async build with polling, past editions, schedule nudges
- Settings (`/settings`) — accordion with 4 cards: Sources, Delivery, Schedule, Your Paper. Deep linking from dashboard via `?open=`. Batch save with undo toast (3s countdown + halftone). Sources managed via catalog checkboxes (no separate list)
- Old routes (`/sources`, `/delivery`, `/editions`) redirect to `/settings` or `/dashboard`
- Landing page and login flow are functional
