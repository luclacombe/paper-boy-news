# web — Next.js Web App

Full-stack web app for Paper Boy News. Deployed on Vercel at `www.paper-boy-news.com`.

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
│   ├── feed-stats.ts  # getFeedStats(), getAllFeedStats() — query feed_stats table
│   ├── account.ts     # getAccountInfo(), changePassword(), deleteAccount()
│   ├── feeds.ts       # CRUD for user_feeds table + cleanOrphanedFeeds()
│   ├── google-oauth.ts
│   ├── onboarding.ts  # completeOnboarding() — saves wizard state to DB
│   ├── opds.ts        # enableOpdsSync(), disableOpdsSync(), regenerateOpdsUrl()
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
│       ├── opds/[token]/feed.xml/     # OPDS catalog feed (token-based auth)
│       ├── opds/[token]/download/[editionId]/ # EPUB download proxy
│       └── smtp-test/ # SMTP connection test (replaces FastAPI)
├── components/
│   ├── ui/            # shadcn/ui primitives (button, card, input, etc.)
│   ├── settings/      # Settings section panels (sources, delivery, schedule, paper, account)
│   ├── app-masthead.tsx      # Newspaper masthead (rendered by dashboard page, not layout)
│   ├── dashboard-client.tsx  # Dashboard interactive UI (deep links to settings via ?open=)
│   ├── save-toast.tsx         # Custom save toast: halftone texture, countdown progress bar, undo
│   ├── settings-accordion.tsx # Accordion cards with colored borders, batch save + undo
│   ├── settings-client.tsx   # Settings page: compact header (← Settings / Sign out) + accordion
│   ├── budget-bar.tsx        # Reading time budget bar (used in sources section + onboarding step 2)
│   ├── feed-badges.tsx       # FeedBadges (per-feed read time badge) + BundleReadTime (per-category total)
│   └── *.tsx          # Shared components (device-card, edition-card, etc.)
├── data/
│   └── feed-catalog.yaml  # Curated feed catalog (~35 feeds, 7 categories)
├── db/
│   ├── index.ts       # Drizzle client (postgres-js driver)
│   ├── schema.ts      # 4 tables: user_profiles, user_feeds, delivery_history, feed_stats
│   └── migrations/    # SQL migrations (RLS policies, triggers)
├── hooks/
│   └── use-onboarding-state.ts  # localStorage persistence for wizard
├── lib/
│   ├── github-dispatch.ts # GitHub Actions repository_dispatch for builds
│   ├── auth.ts        # getAuthUser(), getUserProfile()
│   ├── setup-status.ts # Compute delivery setup completeness
│   ├── download-epub.ts # EPUB download + File System Access API (send to device via USB)
│   ├── constants.ts   # DEVICES, TIMEZONES, DELIVERY_TIMES, EDITION_ROLLOVER_HOUR, BUILD_MESSAGES
│   ├── edition-date.ts # Timezone-aware edition date (5 AM rollover), cutoff checks
│   ├── feed-catalog.ts # Catalog loading + getAllCatalogFeedUrls() for orphan cleanup
│   ├── opds.ts        # buildOpdsFeed() — pure OPDS Atom XML builder
│   ├── reading-time.ts # Reading time helpers: getFrequencyLabel(), formatDailyReadTime(), estimateTotalDailyReading(), hasAnyStats()
│   ├── utils.ts       # cn() helper (clsx + tailwind-merge)
│   └── supabase/
│       ├── admin.ts   # Service role client (for deleteUser, storage cleanup)
│       ├── client.ts  # Browser Supabase client
│       └── server.ts  # Server Supabase client (for Server Components + Actions)
├── proxy.ts           # Auth routing (protect app routes, redirect auth users)
├── types/
│   ├── index.ts       # All TypeScript types
│   └── file-system-access.d.ts  # Chromium File System Access API declarations
└── __tests__/
    ├── setup.ts       # Global test setup (vi.mock for next/headers)
    ├── actions/       # Unit tests for server actions
    └── e2e/           # Integration tests
```

## Database Schema (Drizzle)

4 tables (3 with RLS policies, 1 global):

- **user_profiles** — extends Supabase auth.users (newspaper settings, device, delivery config, Google tokens, onboarding state)
- **user_feeds** — user's RSS feeds (name, url, category, position), FK → user_profiles
- **delivery_history** — build/delivery records (status, article count, sections JSON, EPUB storage path), FK → user_profiles
- **feed_stats** — global per-feed-URL observed metrics (entry counts, freshness, word counts, extraction rates, rolling averages, 30-day history JSONB). No RLS — written by build script (service role), read by Drizzle (direct DB). Keyed by feed URL, not per-user

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
- **Edition model**: edition date = today's calendar date in the user's timezone (no rollover). One per day, enforced by partial unique DB index. `isBeforeEditionCutoff()` checks if before 5 AM local for UI messaging. See `src/lib/edition-date.ts`
- **Build pipeline**: Two-phase: 6 build windows every 4 hours build users in midnight–5 AM local (`BUILD_MODE=build`), deliver at each user's time (`BUILD_MODE=deliver`). Pre-check skips Python setup if no users need building. `getItNow()` action → checks dedup → if `"built"` exists dispatches delivery-only, else creates "building" record → fires `repository_dispatch` → returns immediately. Dashboard polls Supabase every 5s. Status lifecycle: `building → built → delivered` (or `→ failed`)
- **Dashboard state machine**: 9 states computed from edition status, time of day, and setup completeness. Includes `"awaiting-delivery"` for `status="built"` (paper ready, delivery pending). Pure function `getDashboardState()` exported from `dashboard-client.tsx` for testability. **Priority**: active build states (client fetching, DB "building") take precedence over `setup-incomplete`, so mid-build settings changes don't hide the progress bar
- **Settings accordion**: 5 collapsible cards with colored left borders (red/ink/amber/green/caption). One open at a time. Deep linking via `?open=sources|delivery|schedule|paper|account`. First 4 sections use batch save — "Save changes" when dirty, auto-save on collapse. Account section has its own action buttons (password change, delete). Custom save toast (`save-toast.tsx`) with halftone texture, 3s countdown progress bar, and undo. Sources undo uses `setFeeds()` bulk replace; config undo restores previous snapshot. Summary generators exported from `settings-accordion.tsx` for testing. Sources section reports effective (pending-aware) counts to accordion for accurate summary display. **Build locking**: Sources, Delivery, and Schedule sections are locked (dimmed, non-expandable) when `hasActiveBuild()` detects a "building" record for today — prevents settings changes from corrupting in-flight builds
- **Feed stats threading**: `settings/page.tsx` calls `getAllFeedStats()` and threads the result down through `settings-client.tsx` → `settings-accordion.tsx` → `sources-section.tsx`. The same `feedStats` prop flows into onboarding Step 2. Components use `FeedBadges`, `BundleReadTime`, and `BudgetBar` to display per-feed badges, per-bundle totals, and the overall reading time budget bar.
- **Orphaned feed cleanup**: `cleanOrphanedFeeds()` runs on settings page load — removes feeds whose URL is no longer in the catalog (unless category is "Custom"). Handles sources removed from `feed-catalog.yaml` (e.g. Bloomberg, FT)
- **Per-page headers**: AppMasthead is rendered by dashboard (not shared layout), shows user email next to sign out. Settings has its own compact header with back link + sign out
- **Account management**: `account.ts` server actions use admin client (`lib/supabase/admin.ts`) with service role key for `changePassword()` (verifies current password via `signInWithPassword`, then admin update) and `deleteAccount()` (deletes profile via Drizzle cascade, cleans Storage, deletes auth user). Google OAuth users cannot change password
- **Send to device**: File System Access API (`showDirectoryPicker`) lets Chrome/Edge users save EPUBs directly to a USB-mounted e-reader folder. Handle persisted in IndexedDB. Falls back to regular download on unsupported browsers. See `src/lib/download-epub.ts`
- **Wireless sync (KOReader)**: First-class delivery method (`"koreader"` in `DeliveryMethod` union). Per-user OPDS feed with token-based auth (256-bit `crypto.randomBytes`). `/api/opds/[token]/feed.xml` returns Atom XML; `/api/opds/[token]/download/[editionId]` proxies EPUB from Storage. Token auto-generated when user selects "Wireless sync" (`enableOpdsSync()` via `useEffect`, idempotent). `regenerateOpdsUrl()` is immediate action. Device-specific setup instructions (Kobo, reMarkable, Kindle, Other) with links to external KOReader installation guides. Build pipeline treats like `"local"` (skip deliver phase). See `src/lib/opds.ts`, `src/actions/opds.ts`

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

Edition date = **today's calendar date** in the user's configured timezone (no rollover):
- `getEditionDate(timezone)` in `src/lib/edition-date.ts` returns today's date, always.
- `isBeforeEditionCutoff()` checks if before 5 AM local — used for UI messaging (paper building overnight).
- `getItNow()` in `src/actions/build.ts` checks for existing editions before building (dedup guard), then dispatches async build to GitHub Actions.

Dashboard states (in priority order): build-in-progress (client fetching or DB "building") → build-error → fetched-early → awaiting-delivery (DB "built") → delivered → failed → setup-incomplete → pre-build-first / pre-build → ready-first / ready. Active build states take priority over setup-incomplete so mid-build settings changes don't hide the progress bar.

**Scheduled pipeline**: Two-phase — 6 build windows every 4 hours for users in midnight–5 AM local (`BUILD_MODE=build`), deliver at each user's configured time (`BUILD_MODE=deliver`, every 30 min). Status lifecycle: `building → built → delivered` (or `→ failed`). Local/download users skip `"built"` and go straight to `"delivered"`.

## Current Status

- Auth, onboarding, and server actions are complete
- Dashboard (`/dashboard`) — 9-state status card with timezone-aware edition logic, async build with polling, past editions, schedule nudges
- Settings (`/settings`) — accordion with 5 colored-border cards: Sources, Delivery, Schedule, Your Paper, Account. Deep linking from dashboard via `?open=`. Batch save with undo toast (3s countdown + halftone). Sources managed via catalog checkboxes (no separate list). Sources section has inline reading time picker, budget bar (`BudgetBar`), per-feed read time badges (`FeedBadges`), and per-bundle read times (`BundleReadTime`). `feedStats` threaded from page → client → accordion → sources section
- Old routes (`/sources`, `/delivery`, `/editions`) redirect to `/settings` or `/dashboard`
- Landing page and login flow are functional
