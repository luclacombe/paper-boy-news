# Paper Boy Migration — Progress Tracker

> Phases 0–5 are complete.

---

## Phase 1: Database Schema (Supabase + Drizzle) — DONE

- [x] Create Supabase project + copy credentials to `.env.local`
- [x] Fix DATABASE_URL password encoding (special chars `#%*!^` → URL-encoded)
- [x] Add `db:push`, `db:generate`, `db:studio` scripts to `package.json`
- [x] Install `dotenv` + update `drizzle.config.ts` to load `.env.local`
- [x] Run `pnpm db:push` — 3 tables created: `user_profiles`, `user_feeds`, `delivery_history`
- [x] RLS enabled on all 3 tables (5 policies total)
- [x] Auto-create profile trigger (`on_auth_user_created` on `auth.users`)
- [x] Auto-update `updated_at` trigger on `user_profiles`
- [x] Migration SQL saved: `src/db/migrations/001_rls_and_triggers.sql`
- [x] `pnpm build` passes (no regressions)
- [ ] Create `epubs` bucket in Supabase Storage dashboard (manual — set to private)
- [ ] Add Storage RLS policies for `epubs/{userId}/*` (manual — via dashboard)

---

## Phase 2: FastAPI Python Backend — DONE

All files created and verified locally.

### Files created

```
api/
├── main.py              # FastAPI app, CORS, health check
├── models.py            # Pydantic schemas (Build, Deliver, SmtpTest, FeedValidate)
├── auth.py              # JWT middleware (Supabase tokens, dev mode passthrough)
├── routes/
│   ├── __init__.py
│   ├── build.py         # POST /build — EPUB generation + base64 response
│   ├── deliver.py       # POST /deliver — Google Drive, Gmail API, email, local
│   ├── smtp_test.py     # POST /smtp-test — credential testing with error mapping
│   └── feeds.py         # POST /feeds/validate — RSS feed validation
├── requirements.txt     # FastAPI, uvicorn, pydantic, feedparser, etc.
├── Dockerfile           # Python 3.12-slim, PYTHONPATH for paper_boy imports
└── .env.example         # SUPABASE_JWT_SECRET, ALLOWED_ORIGIN, GOOGLE_CREDENTIALS
```

### Verified endpoints

- [x] `GET /health` → `{"status":"ok"}`
- [x] `POST /feeds/validate` → `{"valid":true,"name":"Ars Technica - All content"}`
- [x] `POST /build` → 22KB EPUB, 2 articles, sections with headlines
- [x] `POST /build` (empty feeds) → `{"success":false,"error":"No feeds provided"}`
- [x] `POST /smtp-test` → proper error handling for bad credentials
- [x] 274 existing tests pass
- [x] `pnpm build` passes

### Not yet done

- [ ] API tests (`tests/test_api_*.py`) — deferred to Phase 5
- [ ] Deploy to Railway (Phase 2.14) — do when ready for production

---

## Phase 3: Supabase Auth + Google OAuth — DONE

### 3.1 Supabase Auth setup

- [x] Add login/signup pages (`(auth)/login`, `(auth)/signup`) with email/password
- [x] Create email confirmation route (`api/auth/confirm`) — exchanges token, sets session cookies
- [x] Wire middleware: unauth → `/login`, auth → redirect away from auth pages, protect `/onboarding`
- [x] Add onboarding gate in `(app)/layout.tsx` (async server component, checks `onboarding_complete`)
- [x] Add sign-out button to `app-header.tsx`
- [x] Create shared `lib/auth.ts` — `getAuthUser()` + `getUserProfile()` helpers
- [x] Implement `getUserConfig()` + `isOnboardingComplete()` in `user-config.ts`
- [x] Update landing page CTA to `/signup`
- [ ] Enable email auth provider in Supabase dashboard (manual)
- [ ] Set Site URL + Redirect URL in Supabase Auth settings (manual)

### 3.2 Google OAuth

- [x] `getGoogleAuthUrl()` — builds consent URL with Drive + Gmail scopes
- [x] `api/auth/google/callback/route.ts` — exchanges code for tokens, stores in DB via Drizzle
- [x] `disconnectGoogle()` — nulls `google_tokens` in `user_profiles`
- [x] `hasGmailScope()` / `hasDriveScope()` — reads tokens from DB, checks scopes
- [ ] Configure Google OAuth consent screen + redirect URI in Google Cloud Console (manual)

---

## Phase 4: Wire Server Actions to Database — DONE

### 4.1 User config actions (`actions/user-config.ts`)

- [x] `getUserConfig()` — query `user_profiles` by auth user ID
- [x] `updateUserConfig()` — partial update with field mapping
- [x] `isOnboardingComplete()` — check `onboarding_complete` flag

### 4.2 Feed actions (`actions/feeds.ts`)

- [x] `getFeeds()` — query `user_feeds` ordered by position
- [x] `addFeed()` — insert with auto-incrementing position
- [x] `removeFeed()` — delete by feed ID
- [x] `setFeeds()` — bulk replace (delete all + insert)

### 4.3 Delivery history actions (`actions/delivery-history.ts`)

- [x] `getDeliveryHistory()` — query ordered by date desc, configurable limit
- [x] `addDeliveryRecord()` — insert full record
- [x] `getEditionCount()` — count rows for user

### 4.4 Onboarding action (`actions/onboarding.ts`)

- [x] `completeOnboarding()` — update profile + bulk insert feeds + set `onboarding_complete = true`

### 4.5 Build action (`actions/build.ts`)

- [x] `triggerBuild()` — full pipeline: load config/feeds → POST /build → upload EPUB to Supabase Storage → POST /deliver (if not local) → insert delivery_history → return BuildResult

---

## Phase 5: Testing + Deploy — DONE

### 5.1 Python API tests (pytest)

- [x] Add `httpx` to dev dependencies in `pyproject.toml`
- [x] Add `api_client` + `auth_header` fixtures to `tests/conftest.py`
- [x] `tests/test_api_build.py` — 6 tests (build success, empty feeds, validation, exceptions, file size, defaults)
- [x] `tests/test_api_deliver.py` — 6 tests (local, Google Drive, Gmail routing, email, exceptions, invalid base64)
- [x] `tests/test_api_smtp.py` — 7 tests (SSL, STARTTLS, auth errors 534/535, timeout, DNS, connection refused)
- [x] `tests/test_api_feeds.py` — 5 tests (valid feed, bozo, empty, bozo+entries, exceptions)
- [x] 298 total Python tests pass

### 5.2 Next.js server action tests (Vitest)

- [x] Install `vitest` + `vite-tsconfig-paths`, add `test`/`test:watch` scripts
- [x] Create `vitest.config.ts` + `src/__tests__/setup.ts` (global mocks for next/headers)
- [x] `src/__tests__/actions/user-config.test.ts` — 7 tests
- [x] `src/__tests__/actions/feeds.test.ts` — 9 tests
- [x] `src/__tests__/actions/delivery-history.test.ts` — 6 tests
- [x] `src/__tests__/actions/onboarding.test.ts` — 4 tests
- [x] `src/__tests__/actions/build.test.ts` — 8 tests
- [x] `src/__tests__/actions/google-oauth.test.ts` — 9 tests
- [x] `src/__tests__/e2e/signup-to-deliver.test.ts` — 2 integration tests (full flow + failure)
- [x] 45 total Vitest tests pass

### 5.3 CI workflow

- [x] `.github/workflows/ci.yml` — parallel jobs: `python-tests` + `nextjs-tests`
- [x] Concurrency group cancels stale runs

### 5.4 Deploy API to Railway

- [x] `railway.toml` — Dockerfile path, health check config
- [x] `api/Dockerfile` — use `${PORT:-8000}` for Railway's dynamic port
- [x] `api/main.py` — support `ALLOWED_ORIGINS` (comma-separated) for Vercel production + preview URLs
- [ ] Connect GitHub repo in Railway dashboard (manual)
- [ ] Set env vars: `SUPABASE_JWT_SECRET`, `ALLOWED_ORIGINS`, `GOOGLE_CREDENTIALS` (manual)

### 5.5 Deploy Next.js to Vercel

- [ ] Connect GitHub repo in Vercel dashboard, root directory = `web-next` (manual)
- [ ] Set env vars: Supabase, FastAPI URL, Google OAuth, App URL (manual)
- [ ] Update Supabase Auth settings: Site URL + Redirect URLs (manual)
- [ ] Update Google OAuth redirect URI to Vercel callback URL (manual)
