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
- `test_feeds.py` — RSS fetching + article extraction + cache integration + FT Playwright handler + BoF Arc Publishing handler
- `test_filters.py` — Post-extraction content filters (paywall, junk stripping, section/trailing junk, quality gate)
- `test_images.py` — Image optimization
- `test_main.py` — Build pipeline orchestration + cache threading
- `test_delivery.py` — Delivery backends
- `test_cli.py` — CLI commands

### Build Pipeline Tests
- `test_build_for_users.py` — Build script delivery method snapshotting, mid-build safety, on-demand flow, config construction, helper functions

## Test Patterns

- **Parametrized tests**: `test_filters.py` and `test_feeds.py` use `@pytest.mark.parametrize` for pattern-based tests (junk text removal, normalization rules, caption artifacts). Adding a test case = appending one string to the parametrize list.
- **Section/trailing junk tests**: `TestStripSectionJunk` (20 tests) and `TestStripTrailingJunk` (13 tests) verify structural junk removal patterns (headings + lists, trailing tip-lines, AP section links, Rolling Stone credits, Electrek comments, bounded `next_N` scope, HTML comment handling, SciAm subscription nag, ICN donation block, Morning Brew CTA, Kiplinger subscription, FT recommended newsletters, wire bylines, image credits, author bios, correction notes).
- **Content dedup tests**: `TestStripLedeDupe` (6 tests) and `TestStripFigcaptionParagraphDupe` (4 tests) verify lede and figcaption deduplication.
- **Stale entry tests**: `TestIsStaleEntry` (7 tests) verifies feed freshness gate (old/recent/no-date/boundary/invalid entries, integration with `_fetch_single_feed`).
- **Image recovery tests**: `TestRecoverImagesFromHtml` (11 tests) + `TestDomainSpecificImageRecovery` (3 tests) verifies raw HTML image recovery (already-has-images passthrough, container detection, ad filtering, dedup, lazy-loading, URL validation, cap, AP-specific xpaths).
- **Junk figcaption tests**: `TestJunkFigcaption` (9 tests) verifies detection of UI labels, ALL-CAPS bylines, single-word labels, and preservation of real captions.
- **Bloomberg normalize tests**: `TestBloombergNormalize` (3 tests) verifies ad div removal (with `\xa0`), duplicate figcaption div stripping, and standalone caption div removal.
- **FT handler tests**: Verify Playwright graceful degradation (ImportError → empty list), cache integration (hit skips browser), and filter pipeline on extracted HTML. Uses mocked Playwright to avoid real browser dependency in CI. `TestCleanFtHtml` (9 tests) covers CMS element removal (video, iframe, button), picture unwrapping, n-content-layout flattening, Flourish container removal, figcaption deduplication, and empty li cleanup.
- **BoF handler tests**: Verify Fusion.globalContent JSON parsing, homepage link scraping, and filter pipeline on extracted HTML. Uses mocked `_fetch_page` to avoid real network calls.

## Notes

- `conftest.py` has shared fixtures
- `test_feeds.py` uses `_LONG_CONTENT` (250 words) for mock extraction results — content must pass the 200-word quality gate in `filters.py`
- Legacy FastAPI API tests are in `legacy/api/tests/`
- Next.js tests are separate — they live in `web/src/__tests__/` and use Vitest
