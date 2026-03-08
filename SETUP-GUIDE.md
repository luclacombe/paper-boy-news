# Deployment Setup Guide

Step-by-step guide to configure all secrets and env vars after the Railway → GitHub Actions migration.

---

## 1. Create a GitHub Fine-Grained Personal Access Token

This PAT is used for two things:
- **Vercel** dispatches `repository_dispatch` events to trigger builds
- **GitHub Actions** deletes its own workflow logs (privacy)

### Steps

1. Go to **github.com → Settings → Developer settings → Personal access tokens → Fine-grained tokens**
2. Click **Generate new token**
3. Configure:
   - **Token name**: `paper-boy-build-dispatch`
   - **Expiration**: 90 days (or longer — you'll need to rotate it)
   - **Repository access**: Select **Only select repositories** → choose `paper-boy`
   - **Permissions**:
     - **Contents**: Read and write (needed for `repository_dispatch`)
     - **Actions**: Read and write (needed for log deletion)
   - Leave all other permissions at "No access"
4. Click **Generate token**
5. **Copy the token immediately** — you won't see it again

You'll use this token in two places (steps 2 and 3 below).

---

## 2. Set GitHub Repository Secrets

These are used by the `build-newspaper.yml` workflow when it runs in GitHub Actions.

1. Go to your repo → **Settings → Secrets and variables → Actions**
2. Click **New repository secret** for each:

| Secret name | Where to find the value |
|---|---|
| `SUPABASE_URL` | Supabase dashboard → Project Settings → API → Project URL (the `https://xxx.supabase.co` URL) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase dashboard → Project Settings → API → `service_role` key (the long JWT — **not** the anon key) |
| `GOOGLE_CLIENT_ID` | Google Cloud Console → APIs & Services → Credentials → your OAuth 2.0 Client ID |
| `GOOGLE_CLIENT_SECRET` | Same place → Client secret |
| `GH_PAT` | The fine-grained PAT you created in step 1 |

### Where to find Supabase values

1. Go to [supabase.com/dashboard](https://supabase.com/dashboard)
2. Select your Paper Boy project
3. Go to **Project Settings** (gear icon in sidebar) → **API**
4. **Project URL** = `SUPABASE_URL`
5. Under **Project API keys**, copy the `service_role` key = `SUPABASE_SERVICE_ROLE_KEY`
   - This key bypasses Row Level Security — the build script needs it to read/write any user's data

### Where to find Google OAuth values

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Select your project
3. Go to **APIs & Services → Credentials**
4. Click your **OAuth 2.0 Client ID** (the one used for Drive/Gmail, not sign-in)
5. Copy **Client ID** and **Client secret**

These are needed so the build script can refresh expired Google OAuth tokens when delivering to Drive/Gmail.

### Enable Google APIs

In the same Google Cloud project, enable the APIs Paper Boy uses for delivery:

1. Go to **APIs & Services → Library**
2. Search for and enable **Google Drive API**
3. Search for and enable **Gmail API** (if using email delivery via Gmail)

Without these, OAuth tokens will work for sign-in but delivery will fail with a 403 error.

---

## 3. Set Vercel Environment Variables

These are used by the Next.js server actions to dispatch builds to GitHub Actions.

1. Go to [vercel.com](https://vercel.com) → your Paper Boy project → **Settings → Environment Variables**
2. Add these two variables:

| Variable | Value | Environment |
|---|---|---|
| `GITHUB_PAT` | The fine-grained PAT from step 1 | Production, Preview |
| `GITHUB_REPO` | `your-github-username/paper-boy` (e.g. `luclacombe/paper-boy`) | Production, Preview |

3. **Remove** the old `NEXT_PUBLIC_FASTAPI_URL` variable if it still exists

### Important

- These are **server-side only** variables (no `NEXT_PUBLIC_` prefix) — they're never exposed to the browser
- `GITHUB_REPO` is the `owner/repo` format, not a URL

---

## 4. Set GitHub Actions Log Retention to 1 Day

Extra privacy measure — workflow logs auto-delete after 1 day instead of the default 90 days.

1. Go to your repo → **Settings → Actions → General**
2. Scroll to **Artifact and log retention**
3. Set **Retention period** to **1** day
4. Click **Save**

The workflow also actively deletes its own logs after each run (using the `GH_PAT`), but this is a fallback in case that step fails.

---

## 5. Verify Everything Works

### Test feed validation (no secrets needed)

1. Go to your deployed app → **Settings → Sources**
2. Paste a feed URL (e.g. `https://feeds.arstechnica.com/arstechnica/index`)
3. It should validate and show the feed name — this now runs as a Next.js API route, no Railway needed

### Test SMTP (no secrets needed)

1. Go to **Settings → Delivery** → choose Email with SMTP
2. Enter your SMTP credentials and click **Test connection**
3. Should show success/failure — also runs as a Next.js API route

### Test on-demand build (requires all secrets)

1. Go to **Dashboard** → click **Get it now**
2. You should see the building animation with progress messages
3. After 1–2 minutes, the dashboard should transition to "delivered" or show a download button
4. Check GitHub Actions tab — you should see a `Build Newspaper` workflow run (logs may already be deleted)

### Test scheduled build (requires all secrets)

1. Wait for the next 30-minute cron window (`:00` or `:30` of the hour)
2. If a user's delivery time is within ±15 minutes, a build should auto-trigger
3. Check `delivery_history` in Supabase to confirm

### Troubleshooting

| Symptom | Likely cause |
|---|---|
| "Get it now" fails immediately | `GITHUB_PAT` or `GITHUB_REPO` not set in Vercel |
| Build stays at "building" forever | GitHub Actions workflow failing — check the Actions tab. Likely `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY` not set as GitHub Secrets |
| Build completes but delivery fails | `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` not set as GitHub Secrets, or Google Drive API / Gmail API not enabled in Google Cloud Console |
| Workflow logs visible after run | `GH_PAT` secret missing or doesn't have `actions:write` permission |
| "GitHub dispatch not configured" error | `GITHUB_PAT` env var missing from Vercel |

---

## 6. Clean Up Railway (After Confirming Everything Works)

Once you've verified end-to-end:

1. Go to [railway.app](https://railway.app)
2. Select your Paper Boy project
3. Go to **Settings → Danger Zone → Delete Project**

The `api/` code is preserved in `legacy/api/` if you ever need to reference it.

---

## Summary of All Secrets/Variables

| Name | Where | Purpose |
|---|---|---|
| `GITHUB_PAT` | Vercel + GitHub Secrets (`GH_PAT`) | Dispatch builds + delete logs |
| `GITHUB_REPO` | Vercel | Target repo for dispatch |
| `SUPABASE_URL` | GitHub Secrets | Build script reads/writes DB |
| `SUPABASE_SERVICE_ROLE_KEY` | GitHub Secrets | Bypass RLS for build script |
| `GOOGLE_CLIENT_ID` | GitHub Secrets | Refresh OAuth tokens during delivery |
| `GOOGLE_CLIENT_SECRET` | GitHub Secrets | Refresh OAuth tokens during delivery |
