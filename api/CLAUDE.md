# api — FastAPI Backend

HTTP API wrapping the Paper Boy core Python library. Deployed on Railway via Docker.

## Stack

- **FastAPI** + **uvicorn**
- Imports directly from `paper_boy` core library (`src/paper_boy/`)
- **Pydantic** models for request/response validation
- **Supabase JWT** auth (dev-mode passthrough when no secret configured)
- Deployed via `Dockerfile` → Railway (`railway.toml` in project root)

## Commands

```bash
pip install -r api/requirements.txt
pip install -e "."                      # Install core lib (required)
uvicorn api.main:app --reload           # Dev server (port 8000)
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| POST | `/build` | Build EPUB from feeds config, returns base64-encoded EPUB |
| POST | `/deliver` | Deliver EPUB (Google Drive, Gmail API, SMTP) |
| POST | `/feeds/validate` | Validate an RSS feed URL |
| POST | `/smtp-test` | Test SMTP connection |

## Structure

```
api/
├── main.py            # FastAPI app, CORS config, router includes
├── auth.py            # Supabase JWT verification middleware
├── models.py          # Pydantic models (BuildRequest/Response, DeliverRequest/Response, etc.)
├── requirements.txt   # API-specific deps (fastapi, uvicorn, python-jose, supabase)
├── Dockerfile         # python:3.12-slim, PYTHONPATH=/app/src:/app
├── .env.example
└── routes/
    ├── build.py       # POST /build — calls paper_boy.main.build_newspaper()
    ├── deliver.py     # POST /deliver — Google Drive, Gmail API, SMTP delivery
    ├── feeds.py       # POST /feeds/validate — RSS URL validation
    └── smtp_test.py   # POST /smtp-test — SMTP connection test
```

## Key Details

- CORS origins: `http://localhost:3000` + `ALLOWED_ORIGINS` env var (comma-separated for Vercel preview URLs)
- The Dockerfile sets `PYTHONPATH=/app/src:/app` so both `paper_boy` and `api` packages are importable
- Build endpoint calls `paper_boy.main.build_newspaper()` and returns the EPUB as base64
- Deliver endpoint handles Google Drive (via google-api-python-client), Gmail API, and SMTP
- Tests live in `tests/test_api_*.py` (not in this directory — see `tests/CLAUDE.md`)

## Deployment

- Platform: Railway
- Config: `railway.toml` (project root)
- Health check: `GET /health`
- Production URL: `paper-boy-production.up.railway.app`
- Set `ALLOWED_ORIGINS` to your Vercel production + preview URLs
