# web-next — Next.js Web App

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
pnpm dev:reset        # Reset all users to pre-onboarding state
pnpm dev:reset -- --email dev@paperboy.local  # Reset specific user
pnpm dev:reset -- --onboarding   # Only reset onboarding flag
pnpm dev:reset -- --history      # Only clear delivery history
pnpm dev:reset -- --feeds        # Only clear feeds
pnpm supabase:start   # Start local Supabase (Docker required)
pnpm supabase:stop    # Stop local Supabase
pnpm supabase:reset   # Full DB reset (migrations + seed)
```

## Directory Structure

```
src/
├── actions/           # Server Actions (all data mutations)
│   ├── build.ts       # triggerBuild() — calls FastAPI, stores result in DB
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
│   │   ├── layout.tsx # Auth check, redirects if not onboarded
│   │   ├── dashboard/ # STUB — needs UI
│   │   ├── sources/   # STUB — needs UI
│   │   ├── delivery/  # STUB — needs UI
│   │   └── editions/  # STUB — needs UI
│   └── api/
│       └── auth/      # OAuth callback routes (Supabase + Google)
├── components/
│   ├── ui/            # shadcn/ui primitives (button, card, input, etc.)
│   └── *.tsx          # App components (device-card, edition-card, etc.)
├── data/
│   └── feed-catalog.yaml  # Curated feed catalog (40+ feeds, 7 categories)
├── db/
│   ├── index.ts       # Drizzle client (postgres-js driver)
│   ├── schema.ts      # 3 tables: user_profiles, user_feeds, delivery_history
│   └── migrations/    # SQL migrations (RLS policies, triggers)
├── hooks/
│   └── use-onboarding-state.ts  # localStorage persistence for wizard
├── lib/
│   ├── api-client.ts  # Typed fetch wrapper for FastAPI
│   ├── auth.ts        # getAuthUser(), getUserProfile()
│   ├── constants.ts   # DEVICES, TIMEZONES, DELIVERY_TIMES, BUILD_MESSAGES
│   ├── feed-catalog.ts
│   ├── reading-time.ts
│   ├── utils.ts       # cn() helper (clsx + tailwind-merge)
│   └── supabase/
│       ├── client.ts  # Browser Supabase client
│       └── server.ts  # Server Supabase client (for Server Components + Actions)
├── middleware.ts       # Auth routing (protect app routes, redirect auth users)
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

## Auth Flow

1. User signs up via Google OAuth or email/password (Supabase Auth)
2. Onboarding wizard saves state to localStorage (no auth required for `/onboarding`)
3. Google OAuth redirect → `/onboarding/complete` saves localStorage state to DB
4. Middleware protects `/dashboard`, `/sources`, `/delivery`, `/editions` — requires auth
5. Google Drive/Gmail OAuth is **separate** from sign-in OAuth (scopes: drive.file, gmail.send)

## Key Patterns

- **Server Actions** (`src/actions/`) for all mutations — each gets auth user, queries/mutates via Drizzle
- **Path alias** `@/*` maps to `src/*`
- **Types** centralized in `src/types/index.ts`
- **Supabase clients**: use `server.ts` in Server Components/Actions, `client.ts` in Client Components
- **FastAPI calls** go through `src/lib/api-client.ts` (typed fetch wrapper)
- **Build pipeline**: `triggerBuild()` action → FastAPI `/build` → FastAPI `/deliver` → stores result in delivery_history

## Design System

- Newspaper aesthetic: Playfair Display (headings), Libre Baskerville (body), Source Sans 3 (UI), JetBrains Mono (code)
- Color palette defined in `globals.css`: newsprint (#FAF8F5), ink (#1B1B1B), edition red, delivered green, building amber
- Lucide icons via `lucide-react`
- shadcn/ui components in `src/components/ui/`

## Environment Variables

See `.env.example` for cloud vars, `.env.local.example` for local Supabase:
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL` (Supabase PostgreSQL connection string)
- `NEXT_PUBLIC_FASTAPI_URL` (Railway API URL)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (for Drive/Gmail OAuth)
- `NEXT_PUBLIC_APP_URL` (for OAuth redirects)

**Env file strategy**:
- `.env.local` — active env (used by Next.js, gitignored)
- `.env.local.dev` — local Supabase credentials (gitignored)
- `.env.local.cloud` — cloud Supabase credentials (gitignored)
- `.env.local.example` — local Supabase template with default keys (committed)
- `.env.example` — cloud env template (committed)

## Current Status

- Auth, onboarding, server actions, and API integration are complete
- App pages (`/dashboard`, `/sources`, `/delivery`, `/editions`) are **stubs** — placeholder text only, UI needs to be built
- Landing page and login flow are functional
