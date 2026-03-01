# Deployment Research & Migration Guide

Research into deployment options for making Paper Boy available as a hosted website, moving beyond the current clone-install-run workflow.

## Goals

- Host Paper Boy as a public website with a custom domain (no branded URLs)
- Persistent data storage (user config, delivery history, EPUB files)
- Daily scheduled newspaper builds
- Low cost (ideally free or under $5/month)
- Ability to host other projects on the same infrastructure in the future

## Architecture Decision

Paper Boy's current JSON file persistence (`web/services/database.py`) doesn't survive restarts on most hosting platforms. The solution is **Supabase** as the persistence backend, which unlocks free/cheap hosting options that lack persistent filesystems.

```
User → Hosted Web App (Streamlit) → Supabase (DB + file storage)
                                  → Google Drive (EPUB delivery)
GitHub Actions → Daily builds     → Supabase (keeps project alive)
```

---

## Top Two Options

### Option A: Streamlit Community Cloud + Supabase + GitHub Actions

**Cost: $0/month** (custom domain requires Streamlit Teams at $25/month)

| Layer | Service | Role |
|-------|---------|------|
| Frontend | Streamlit Community Cloud | Web app UI, auto-deploys from GitHub |
| Database | Supabase (Postgres) | User config, delivery history |
| File storage | Supabase Storage | EPUB files |
| Scheduled builds | GitHub Actions | Daily 6am cron |
| EPUB delivery | Google Drive API | Kobo sync |

**How deployment works:**
1. Connect the GitHub repo at `share.streamlit.io`
2. Select `web/app.py` as the entry point
3. Add secrets (Supabase URL/key, Google credentials) via Streamlit's secrets UI
4. Every push to `main` auto-redeploys

**Pros:**
- Completely free
- Zero infrastructure to manage
- Native Streamlit hosting (guaranteed compatibility)
- Auto-deploy on push
- Built-in secrets management

**Cons:**
- App sleeps after ~7 days without visitors (30-60s cold start on wake)
- ~1 GB RAM limit (should be sufficient for EPUB builds)
- Custom domains require paid plan ($25/month for Teams)
- URL is `your-app.streamlit.app` on free tier
- No control over the runtime environment

**Best for:** Free hosting with minimal ops. Accept the branded URL or pay $25/month for custom domain.

---

### Option B: Hetzner Cloud VPS + Supabase + GitHub Actions

**Cost: ~$4.50/month** (VPS + domain)

| Layer | Service | Cost |
|-------|---------|------|
| VPS | Hetzner CX22 (2 vCPU, 4 GB RAM, 40 GB SSD) | EUR 3.29/month (~$3.50) |
| Domain | Any registrar (.com) | ~$12/year (~$1/month) |
| Database | Supabase free tier | $0 |
| SSL | Let's Encrypt (via Caddy) | $0 |
| Scheduled builds | GitHub Actions or server cron | $0 |
| EPUB delivery | Google Drive API | $0 |

**How deployment works:**
1. Provision a Hetzner CX22 VPS
2. Install Docker + Caddy (reverse proxy with auto-SSL)
3. Run Paper Boy as a Docker container
4. Point your domain's DNS to the VPS IP
5. Caddy handles SSL certificates automatically

**Server architecture:**
```
yourdomain.com (DNS A record → Hetzner VPS static IP)
│
├── Caddy (reverse proxy + automatic Let's Encrypt SSL)
│   ├── news.yourdomain.com   → Paper Boy (Docker, port 8501)
│   ├── app2.yourdomain.com   → Future project (Docker, port XXXX)
│   └── app3.yourdomain.com   → Future project (Docker, port XXXX)
│
├── Docker containers (each app isolated)
└── cron or GitHub Actions (daily newspaper builds)
```

**Caddy config example (`/etc/caddy/Caddyfile`):**
```
news.yourdomain.com {
    reverse_proxy localhost:8501
}

app2.yourdomain.com {
    reverse_proxy localhost:3000
}
```

**Docker run command:**
```bash
docker run -d \
  --name paper-boy \
  --restart unless-stopped \
  -p 8501:8501 \
  -e SUPABASE_URL=https://xxx.supabase.co \
  -e SUPABASE_KEY=eyJ... \
  -e GOOGLE_CREDENTIALS='{"type":"service_account",...}' \
  ghcr.io/luclacombe/paper-boy:latest
```

**Pros:**
- Custom domain with proper SSL
- Full control over the server
- Can host unlimited additional projects (2 vCPU + 4 GB RAM is plenty for several small apps)
- 99.9% uptime SLA, data center networking
- No sleep/spin-down behavior
- Static IP, professional setup

**Cons:**
- Requires initial server setup (Docker, Caddy, firewall)
- You manage OS updates and security
- Monthly cost (~$4.50/month)
- Hetzner is EU-based (US data centers available in Ashburn and Hillsboro)

**Best for:** Professional hosting with custom domain, multi-project capability, and full control.

---

## Comparison

| Factor | Streamlit Cloud | Hetzner VPS |
|--------|----------------|-------------|
| Monthly cost | $0 (branded URL) / $25 (custom domain) | ~$4.50 |
| Custom domain | Paid only | Yes |
| Uptime | Sleeps after 7 days idle | Always on |
| RAM | ~1 GB | 4 GB |
| Multiple sites | No | Yes |
| Setup effort | 5 minutes | 1-2 hours |
| Maintenance | Zero | OS updates, monitoring |
| Control | None | Full |

---

## Supabase: The Persistence Layer (Required for Both Options)

### Free Tier Limits

| Resource | Free Limit | Paper Boy Usage |
|----------|-----------|-----------------|
| Database (Postgres) | 500 MB | ~1 MB |
| File storage | 1 GB | ~150 MB (30 days at 5 MB/edition) |
| Storage egress | 2 GB/month | ~150 MB/month |
| API requests | Unlimited | A few per day |
| Auth users | 50,000 MAU | 1 |
| Max file upload | 50 MB | 1-5 MB EPUBs |
| Active projects | 2 | 1 |

### Auto-Pause Warning

Free tier projects pause after **7 days of no API requests**. Paper Boy's daily GitHub Actions build will hit the Supabase API every day, preventing this. If Actions is ever disabled, add a keep-alive cron job:

```yaml
# .github/workflows/keep-alive.yml
name: Keep Supabase Alive
on:
  schedule:
    - cron: "0 0 */3 * *"  # Every 3 days
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: |
          curl -s "${{ secrets.SUPABASE_URL }}/rest/v1/" \
            -H "apikey: ${{ secrets.SUPABASE_KEY }}" \
            -H "Authorization: Bearer ${{ secrets.SUPABASE_KEY }}"
```

### Database Schema

```sql
-- User configuration
CREATE TABLE user_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT UNIQUE NOT NULL,
    title TEXT DEFAULT 'Morning Digest',
    feeds JSONB DEFAULT '[]'::jsonb,
    delivery_method TEXT DEFAULT 'local',
    google_drive_folder TEXT DEFAULT 'Rakuten Kobo',
    max_articles_per_feed INTEGER DEFAULT 10,
    include_images BOOLEAN DEFAULT TRUE,
    delivery_time TEXT DEFAULT '06:00',
    language TEXT DEFAULT 'en',
    onboarding_complete BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Delivery history
CREATE TABLE delivery_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES user_config(user_id),
    built_at TIMESTAMPTZ DEFAULT now(),
    title TEXT,
    article_count INTEGER,
    feed_count INTEGER,
    file_size_bytes BIGINT,
    file_path TEXT,          -- path in Supabase Storage bucket
    status TEXT DEFAULT 'built',
    delivery_method TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_history_user_date ON delivery_history(user_id, built_at DESC);
```

### Storage Bucket

- **Bucket name:** `editions`
- **Visibility:** Private (signed URLs for downloads)
- **Allowed MIME types:** `application/epub+zip`
- **Path convention:** `{user_id}/{year}/{month}/morning-digest-{date}.epub`

---

## Migration Plan: database.py (JSON Files → Supabase)

The migration is contained to `web/services/database.py`. The public API stays identical — only internal implementation changes.

### Step 1: Add Supabase dependency

Add to `web/requirements.txt`:
```
supabase>=2.0.0
```

### Step 2: Initialize Supabase client

```python
import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def _get_supabase() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )
```

### Step 3: Replace file I/O with Supabase calls

Current function signatures remain the same. Internal changes:

```python
# get_user_config() — read from Supabase, cache in session_state
def get_user_config(user_id: str = "default") -> dict:
    if "user_config" not in st.session_state:
        db = _get_supabase()
        result = db.table("user_config").select("*").eq("user_id", user_id).execute()
        if result.data:
            st.session_state["user_config"] = result.data[0]
        else:
            st.session_state["user_config"] = DEFAULT_CONFIG.copy()
    return st.session_state["user_config"]

# save_user_config() — upsert to Supabase
def save_user_config(config: dict, user_id: str = "default"):
    db = _get_supabase()
    config["user_id"] = user_id
    config["updated_at"] = datetime.utcnow().isoformat()
    db.table("user_config").upsert(config, on_conflict="user_id").execute()
    st.session_state["user_config"] = config

# add_delivery_record() — insert to Supabase
def add_delivery_record(record: dict, user_id: str = "default"):
    db = _get_supabase()
    record["user_id"] = user_id
    db.table("delivery_history").insert(record).execute()

# get_delivery_history() — query from Supabase
def get_delivery_history(user_id: str = "default") -> list[dict]:
    db = _get_supabase()
    result = (
        db.table("delivery_history")
        .select("*")
        .eq("user_id", user_id)
        .order("built_at", desc=True)
        .limit(30)
        .execute()
    )
    return result.data
```

### Step 4: EPUB storage

After building an EPUB, upload to Supabase Storage instead of saving locally:

```python
def upload_epub(file_path: str, date: str, user_id: str = "default") -> str:
    """Upload EPUB to Supabase Storage. Returns the storage path."""
    db = _get_supabase()
    storage_path = f"{user_id}/{date}/morning-digest-{date}.epub"
    with open(file_path, "rb") as f:
        db.storage.from_("editions").upload(
            path=storage_path,
            file=f,
            file_options={"content-type": "application/epub+zip"},
        )
    return storage_path

def get_epub_download_url(storage_path: str, expires_in: int = 3600) -> str:
    """Generate a signed download URL for an EPUB."""
    db = _get_supabase()
    result = db.storage.from_("editions").create_signed_url(storage_path, expires_in)
    return result["signedURL"]
```

### Step 5: Secrets configuration

For **Streamlit Community Cloud**, add secrets via the dashboard UI.

For **Hetzner VPS**, pass as environment variables to Docker or use `.streamlit/secrets.toml`:

```toml
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "eyJhbGciOi..."
```

### Step 6: EPUB cleanup

To stay within Supabase's 1 GB storage limit, delete old editions:

```python
def cleanup_old_editions(keep_days: int = 30, user_id: str = "default"):
    """Delete editions older than keep_days from Supabase Storage."""
    db = _get_supabase()
    cutoff = (datetime.utcnow() - timedelta(days=keep_days)).isoformat()
    old_records = (
        db.table("delivery_history")
        .select("id, file_path")
        .eq("user_id", user_id)
        .lt("built_at", cutoff)
        .execute()
    )
    for record in old_records.data:
        if record.get("file_path"):
            db.storage.from_("editions").remove([record["file_path"]])
        db.table("delivery_history").delete().eq("id", record["id"]).execute()
```

---

## Hetzner VPS Setup Checklist

If choosing the Hetzner option, the full setup is:

### One-time server setup
- [ ] Create Hetzner Cloud account
- [ ] Provision CX22 VPS (select US or EU region)
- [ ] SSH in, update packages (`apt update && apt upgrade`)
- [ ] Install Docker (`curl -fsSL https://get.docker.com | sh`)
- [ ] Install Caddy (`apt install caddy`)
- [ ] Configure firewall (allow 80, 443, 22 only)
- [ ] Set up unattended security updates (`apt install unattended-upgrades`)

### Domain setup
- [ ] Register a domain (Cloudflare, Namecheap, etc.)
- [ ] Add DNS A record pointing to VPS IP
- [ ] Configure Caddy reverse proxy (auto-SSL via Let's Encrypt)

### Supabase setup
- [ ] Create Supabase project at supabase.com
- [ ] Run the SQL schema (user_config + delivery_history tables)
- [ ] Create `editions` storage bucket (private)
- [ ] Copy project URL and anon key

### Paper Boy deployment
- [ ] Build and push Docker image to ghcr.io (via GitHub Actions)
- [ ] Run container on VPS with environment variables
- [ ] Verify the app is accessible at your domain

### GitHub Actions updates
- [ ] Add Supabase secrets to GitHub repo (SUPABASE_URL, SUPABASE_KEY)
- [ ] Update daily-news.yml to use Supabase for build records

---

## Streamlit Cloud Setup Checklist

If choosing Streamlit Community Cloud:

### Supabase setup
- [ ] Create Supabase project at supabase.com
- [ ] Run the SQL schema (user_config + delivery_history tables)
- [ ] Create `editions` storage bucket (private)

### Streamlit Cloud deployment
- [ ] Go to share.streamlit.io
- [ ] Connect GitHub repo, select `web/app.py`
- [ ] Add secrets: SUPABASE_URL, SUPABASE_KEY, GOOGLE_CREDENTIALS

### GitHub Actions updates
- [ ] Add Supabase secrets to GitHub repo
- [ ] Update daily-news.yml to use Supabase for build records

---

## Other Options Evaluated (Not Selected)

These were researched but not chosen as primary options:

| Option | Cost | Why Not |
|--------|------|---------|
| **Hugging Face Spaces** | Free | Branded URL, sleeps after 48h, no custom domain |
| **Railway** | $5-10/month | More expensive than Hetzner, less flexibility |
| **Render** | $0-7/month | Free tier spins down after 15 min, always-on is $7/month |
| **Fly.io** | $3-6/month | Requires Docker, no built-in cron, small free VMs |
| **Google Cloud Run** | $0-3/month | Complex setup (GCP + Docker), overkill for single app |
| **Heroku** | $5-7/month | No free tier, no persistent filesystem, declining platform |
| **Raspberry Pi** | ~$100 one-time | Depends on home internet/power, security concerns, networking complexity |
| **Oracle Cloud free tier** | Free forever | ARM instances hard to provision, confusing UI, risk of account termination |
| **PythonAnywhere** | $5/month | Cannot run Streamlit (no WebSocket support) |
| **GitHub Codespaces** | Free (120 hrs/mo) | Ephemeral dev environment, not for hosting |
| **Streamlit Cloud (paid)** | $25/month | Too expensive just for a custom domain |

### Distribution options evaluated

| Option | Why Not (for now) |
|--------|-------------------|
| **PyPI** (`pip install paper-boy`) | Good for CLI distribution but doesn't solve web hosting |
| **Docker Hub / ghcr.io** | Useful for Hetzner deployment, not a user-facing solution |
| **Homebrew** | High maintenance, macOS only, worth revisiting if project grows |
| **One-click deploy buttons** | Good supplement to README, not a primary strategy |
| **PyInstaller** | Works for CLI only, Streamlit bundling is fragile |
| **Electron/Tauri desktop wrapper** | Massive effort, fragile Python embedding, not worth it |
