# tests — Python Test Suite

pytest tests for the core Python library and FastAPI backend.

## Run

```bash
pytest                           # Run all tests
pytest tests/ -v --tb=short      # Verbose with short tracebacks (CI mode)
pytest tests/test_epub.py        # Single file
pytest -k "test_build"           # By name pattern
```

## Organization

### Core Library Tests
- `test_config.py` — YAML config loading + validation
- `test_cover.py` — Cover image generation
- `test_epub.py` — EPUB creation + metadata
- `test_feeds.py` — RSS fetching + article extraction
- `test_images.py` — Image optimization
- `test_main.py` — Build pipeline orchestration
- `test_delivery.py` — Delivery backends
- `test_cli.py` — CLI commands
- `test_builder.py` — Builder service

### FastAPI API Tests
- `test_api_build.py` — `POST /build` endpoint
- `test_api_deliver.py` — `POST /deliver` endpoint
- `test_api_feeds.py` — `POST /feeds/validate` endpoint
- `test_api_smtp.py` — `POST /smtp-test` endpoint

### Web Service Tests (legacy Streamlit services)
- `test_database.py` — JSON persistence
- `test_feed_catalog.py` — Feed catalog loading
- `test_github_actions.py` — GitHub Actions integration
- `test_google_oauth.py` — Google OAuth flow
- `test_gmail_sender.py` — Gmail API sending
- `test_smtp_test.py` — SMTP testing
- `test_dashboard.py` — Dashboard logic

## Notes

- `conftest.py` has shared fixtures
- API tests require `PYTHONPATH` to include both `src/` and project root (handled in CI)
- Next.js tests are separate — they live in `web-next/src/__tests__/` and use Vitest
