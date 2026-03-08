"""Tests for the in-memory content cache."""

from __future__ import annotations

from paper_boy.cache import CacheStats, ContentCache


class TestContentCacheInit:
    def test_starts_empty(self):
        cache = ContentCache()
        assert cache.stats == CacheStats()

    def test_stats_all_zero(self):
        stats = CacheStats()
        assert stats.feed_hits == 0
        assert stats.feed_misses == 0
        assert stats.article_hits == 0
        assert stats.article_misses == 0
        assert stats.image_hits == 0
        assert stats.image_misses == 0


class TestFeedCache:
    def test_miss_returns_none(self):
        cache = ContentCache()
        assert cache.get_feed("https://example.com/rss") is None

    def test_hit_returns_entries(self):
        cache = ContentCache()
        entries = [{"title": "Article 1"}, {"title": "Article 2"}]
        cache.set_feed("https://example.com/rss", entries)
        assert cache.get_feed("https://example.com/rss") == entries

    def test_stats_tracking(self):
        cache = ContentCache()
        cache.get_feed("https://miss.com/rss")
        cache.set_feed("https://hit.com/rss", [])
        cache.get_feed("https://hit.com/rss")
        assert cache.stats.feed_misses == 1
        assert cache.stats.feed_hits == 1


class TestArticleCache:
    def test_miss_returns_false_none(self):
        cache = ContentCache()
        found, html = cache.get_article("https://example.com/article", True)
        assert found is False
        assert html is None

    def test_hit_returns_true_and_html(self):
        cache = ContentCache()
        cache.set_article("https://example.com/article", True, "<p>Content</p>")
        found, html = cache.get_article("https://example.com/article", True)
        assert found is True
        assert html == "<p>Content</p>"

    def test_caches_none_for_failed_extraction(self):
        cache = ContentCache()
        cache.set_article("https://example.com/fail", True, None)
        found, html = cache.get_article("https://example.com/fail", True)
        assert found is True
        assert html is None

    def test_different_include_images_separate_keys(self):
        cache = ContentCache()
        cache.set_article("https://example.com/a", True, "<p>With images</p>")
        cache.set_article("https://example.com/a", False, "<p>Without images</p>")

        _, html_with = cache.get_article("https://example.com/a", True)
        _, html_without = cache.get_article("https://example.com/a", False)
        assert html_with == "<p>With images</p>"
        assert html_without == "<p>Without images</p>"

    def test_stats_tracking(self):
        cache = ContentCache()
        cache.get_article("https://miss.com/a", True)
        cache.set_article("https://hit.com/a", True, "<p>OK</p>")
        cache.get_article("https://hit.com/a", True)
        assert cache.stats.article_misses == 1
        assert cache.stats.article_hits == 1


class TestImageCache:
    def test_miss_returns_false_none(self):
        cache = ContentCache()
        found, data = cache.get_image("https://example.com/img.jpg")
        assert found is False
        assert data is None

    def test_hit_returns_true_and_bytes(self):
        cache = ContentCache()
        cache.set_image("https://example.com/img.jpg", b"jpeg-data")
        found, data = cache.get_image("https://example.com/img.jpg")
        assert found is True
        assert data == b"jpeg-data"

    def test_caches_none_for_failed_download(self):
        cache = ContentCache()
        cache.set_image("https://example.com/broken.jpg", None)
        found, data = cache.get_image("https://example.com/broken.jpg")
        assert found is True
        assert data is None

    def test_stats_tracking(self):
        cache = ContentCache()
        cache.get_image("https://miss.com/img.jpg")
        cache.set_image("https://hit.com/img.jpg", b"data")
        cache.get_image("https://hit.com/img.jpg")
        assert cache.stats.image_misses == 1
        assert cache.stats.image_hits == 1


class TestLogStats:
    def test_log_stats_does_not_raise(self):
        cache = ContentCache()
        cache.get_feed("https://a.com/rss")
        cache.set_feed("https://a.com/rss", [])
        cache.get_feed("https://a.com/rss")
        cache.log_stats()
