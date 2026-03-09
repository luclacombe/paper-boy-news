# tests — Python Test Suite

pytest tests for the core Python library.

## Run

```bash
pytest                           # Run all tests
pytest tests/ -v --tb=short      # Verbose with short tracebacks (CI mode)
pytest tests/test_epub.py        # Single file
pytest -k "test_build"           # By name pattern
```

## Organization

### Core Library Tests
- `test_cache.py` — In-memory content cache (ContentCache)
- `test_config.py` — YAML config loading + validation
- `test_cover.py` — Cover image generation
- `test_epub.py` — EPUB creation + metadata
- `test_feeds.py` — RSS fetching + article extraction + cache integration
- `test_images.py` — Image optimization
- `test_main.py` — Build pipeline orchestration + cache threading
- `test_delivery.py` — Delivery backends
- `test_cli.py` — CLI commands

### Build Pipeline Tests
- `test_build_for_users.py` — Build script delivery method snapshotting, mid-build safety, on-demand flow, config construction, helper functions

## Notes

- `conftest.py` has shared fixtures
- Legacy FastAPI API tests are in `legacy/api/tests/`
- Next.js tests are separate — they live in `web/src/__tests__/` and use Vitest
