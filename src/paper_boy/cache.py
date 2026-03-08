"""In-memory content cache for deduplicating network I/O across user builds."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_SENTINEL = object()


@dataclass
class CacheStats:
    """Hit/miss counters per cache layer."""

    feed_hits: int = 0
    feed_misses: int = 0
    article_hits: int = 0
    article_misses: int = 0
    image_hits: int = 0
    image_misses: int = 0


class ContentCache:
    """Shared in-memory cache scoped to a single scheduled run.

    Three layers:
    - feeds: feed_url -> list of parsed entries (feedparser dicts)
    - articles: (article_url, include_images) -> extracted HTML str or None
    - images: image_url -> raw downloaded bytes or None
    """

    def __init__(self) -> None:
        self._feeds: dict[str, list] = {}
        self._articles: dict[tuple[str, bool], str | None] = {}
        self._images: dict[str, bytes | None] = {}
        self.stats = CacheStats()

    # -- Feed layer --

    def get_feed(self, url: str) -> list | None:
        """Return cached feed entries or None on miss."""
        entries = self._feeds.get(url, _SENTINEL)
        if entries is _SENTINEL:
            self.stats.feed_misses += 1
            return None
        self.stats.feed_hits += 1
        return entries  # type: ignore[return-value]

    def set_feed(self, url: str, entries: list) -> None:
        """Cache parsed feed entries."""
        self._feeds[url] = entries

    # -- Article layer --

    def get_article(self, url: str, include_images: bool) -> tuple[bool, str | None]:
        """Return (found, html) — found=True even when html is None (cached failure)."""
        key = (url, include_images)
        value = self._articles.get(key, _SENTINEL)
        if value is _SENTINEL:
            self.stats.article_misses += 1
            return False, None
        self.stats.article_hits += 1
        return True, value  # type: ignore[return-value]

    def set_article(self, url: str, include_images: bool, html: str | None) -> None:
        """Cache extracted article HTML (or None for failed extraction)."""
        self._articles[(url, include_images)] = html

    # -- Image layer --

    def get_image(self, url: str) -> tuple[bool, bytes | None]:
        """Return (found, bytes) — found=True even when bytes is None (cached failure)."""
        value = self._images.get(url, _SENTINEL)
        if value is _SENTINEL:
            self.stats.image_misses += 1
            return False, None
        self.stats.image_hits += 1
        return True, value  # type: ignore[return-value]

    def set_image(self, url: str, data: bytes | None) -> None:
        """Cache raw image bytes (or None for failed download)."""
        self._images[url] = data

    # -- Reporting --

    def log_stats(self) -> None:
        """Log cache hit/miss summary."""
        s = self.stats
        total_hits = s.feed_hits + s.article_hits + s.image_hits
        logger.info(
            "Cache stats — feeds: %d/%d hits/misses, "
            "articles: %d/%d, images: %d/%d (total saved: %d requests)",
            s.feed_hits,
            s.feed_misses,
            s.article_hits,
            s.article_misses,
            s.image_hits,
            s.image_misses,
            total_hits,
        )
