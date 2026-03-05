# Paper Boy

Automated morning newspaper generator for e-readers (Kobo, Kindle, etc).

Fetches news from RSS feeds, compiles them into a well-formatted EPUB, and delivers it to your e-reader. Supports **Kobo** (via Google Drive), **Kindle** (via Send-to-Kindle email), **reMarkable**, and any EPUB-compatible device. Use the **web app** for a visual experience or the **CLI** for automation.

## How It Works

1. Pick your sources from 40+ curated feeds or add your own RSS URLs
2. Choose your e-reader — Kobo, Kindle, reMarkable, or other
3. Build your newspaper — articles are extracted, images optimized for e-ink
4. Deliver automatically to your device (Google Drive, email) or download the EPUB

## Quick Start

### Web App (Recommended)

**[→ paper-boy-news.vercel.app](https://paper-boy-news.vercel.app)**

Sign up for free and the onboarding wizard walks you through everything — pick your sources, configure delivery, and build your first edition in minutes.

#### Local development

```bash
# Prerequisites: Docker Desktop, Node.js 20+, pnpm, Supabase CLI

git clone https://github.com/luclacombe/paper-boy.git
cd paper-boy

# Start local Supabase (Postgres + Auth + Studio)
supabase start

# Start the web app
cd web-next
cp .env.local.example .env.local     # fill in local Supabase URLs (see web-next/CLAUDE.md)
pnpm install
pnpm dev                              # http://localhost:3000
```

Test accounts (password: `password123`): `dev@paperboy.local` · `onboarded@paperboy.local`

### CLI

```bash
# Install
pip install -e .

# Copy and customize config
cp config.example.yaml config.yaml

# Build a newspaper locally
paper-boy build

# Build and deliver to Google Drive
paper-boy deliver
```

### Automated Daily Delivery (GitHub Actions)

This repo includes a workflow that runs at 6:00 AM UTC daily.

1. **Fork this repo** (or use it as-is)
2. **Set up Google Drive credentials** — see [Google Drive Setup](#google-drive-setup)
3. **Add the secret** to your repo: Settings > Secrets > Actions > `GOOGLE_CREDENTIALS`
4. **(Optional)** Commit a custom `config.yaml` to override the default feeds
5. The workflow runs automatically, or trigger it manually from the Actions tab

## Web App Features

- **Onboarding wizard** — 4-step setup: choose your device, pick your sources, configure delivery, build your first edition
- **Dashboard** — Build editions, see article headlines, first-run setup summary, trigger delivery
- **Source management** — Browse 40+ curated feeds across 7 categories, starter bundles, or add custom RSS URLs
- **Feed health** — See which sources are active or failing after each build
- **Starter bundles** — Morning Briefing, Tech & Science, Business & Finance (with two-way sync)
- **Reading time** — Choose how long you want to read (5–30 min), mapped to article count automatically
- **Multi-device delivery** — Kobo (Google Drive), Kindle (Send-to-Kindle email), reMarkable (download), or manual download
- **Delivery settings** — Device, method, schedule, newspaper title, and reading time configuration
- **Edition history** — Browse and download past editions
- **GitHub Actions** — Trigger remote builds from the dashboard

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize:

```yaml
newspaper:
  title: "Morning Digest"
  language: "en"
  max_articles_per_feed: 10
  include_images: true

feeds:
  - name: "World News"
    url: "https://www.theguardian.com/world/rss"
  - name: "Technology"
    url: "https://feeds.arstechnica.com/arstechnica/index"

delivery:
  method: "google_drive"  # "google_drive", "email", or "local"
  device: "kobo"           # "kobo", "kindle", "remarkable", or "other"
  google_drive:
    folder_name: "Rakuten Kobo"
  email:                   # For Send-to-Kindle or any email delivery
    smtp_host: "smtp.gmail.com"
    smtp_port: 465
    sender: ""
    password: ""           # App password, not your regular password
    recipient: ""          # e.g., your-name@kindle.com
  keep_days: 30
```

## CLI Reference

```bash
paper-boy build                          # Build EPUB locally
paper-boy deliver                        # Build + deliver (Google Drive, email, etc.)
paper-boy build --config my-config.yaml  # Use custom config
paper-boy build --output ./output/       # Custom output path
paper-boy -v build                       # Verbose logging
```

## Google Drive Setup

Paper Boy uses a Google service account to upload EPUBs to Google Drive.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable the **Google Drive API**
4. Create a **Service Account** (IAM & Admin > Service Accounts)
5. Create a JSON key for the service account
6. **Share your Google Drive folder** (e.g., "Rakuten Kobo") with the service account email
7. For GitHub Actions: add the JSON key contents as a repo secret named `GOOGLE_CREDENTIALS`
8. For local use: save the JSON file as `credentials.json` in the project root

## Kindle Setup (Send-to-Kindle)

Paper Boy can email EPUBs directly to your Kindle. Amazon accepts EPUB files natively.

1. Find your Kindle email address in [Manage Your Content and Devices](https://www.amazon.com/hz/mycd/myx) → Preferences → Personal Document Settings
2. Add your sending email to the **Approved Personal Document E-mail List** on the same page
3. For Gmail: create an [App Password](https://myaccount.google.com/apppasswords) (requires 2-Step Verification)
4. Configure in the web app (Delivery settings) or in `config.yaml`:
   ```yaml
   delivery:
     method: "email"
     device: "kindle"
     email:
       smtp_host: "smtp.gmail.com"
       smtp_port: 465
       sender: "your-email@gmail.com"
       password: "your-app-password"
       recipient: "your-kindle@kindle.com"
   ```

## Tech Stack

| Component | Stack |
|-----------|-------|
| Web app | Next.js 16, React 19, TypeScript (strict), Tailwind CSS v4, shadcn/ui |
| Auth | Supabase Auth (Google OAuth + email/password) |
| Database | Supabase PostgreSQL via Drizzle ORM |
| API | FastAPI, deployed on Railway |
| Core library | Python 3.9+, feedparser, trafilatura, ebooklib, Pillow |
| Package manager | pnpm (web), pip (Python) |

## Development

```bash
# Python core library
pip install -e ".[dev]"
pytest

# Next.js web app (requires local Supabase — see Local Development above)
cd web-next
pnpm dev        # dev server
pnpm test       # Vitest
pnpm build      # production build
pnpm lint       # ESLint

# FastAPI backend
uvicorn api.main:app --reload   # http://localhost:8000
```

See [web-next/CLAUDE.md](web-next/CLAUDE.md) and [api/CLAUDE.md](api/CLAUDE.md) for detailed setup guides.

## License

MIT
