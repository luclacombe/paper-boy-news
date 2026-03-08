"""Tests for RSS feed fetching and article extraction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from paper_boy.cache import ContentCache
from paper_boy.feeds import (
    _download_image,
    _extract_article,
    _fetch_single_feed,
    _get_feed_content,
    _should_skip_image,
    fetch_feeds,
)


# --- Helpers ---


def _make_feed_entry(
    title="Test Article",
    link="https://example.com/article/1",
    author=None,
    authors=None,
    published=None,
    updated=None,
    summary="",
    content=None,
):
    """Build a dict that mimics a feedparser entry."""
    entry = {"title": title, "link": link, "summary": summary}
    if author is not None:
        entry["author"] = author
    if authors is not None:
        entry["authors"] = authors
    if published is not None:
        entry["published"] = published
    if updated is not None:
        entry["updated"] = updated
    if content is not None:
        entry["content"] = content
    return entry


def _make_parsed_feed(entries=None, bozo=False, bozo_exception=None):
    """Build a mock that mimics feedparser.parse() return value."""
    feed = MagicMock()
    feed.entries = entries if entries is not None else []
    feed.bozo = bozo
    feed.bozo_exception = bozo_exception
    return feed


# --- TestFetchFeeds ---


class TestFetchFeeds:
    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>Full text.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html>page</html>")
    @patch("paper_boy.feeds.feedparser.parse")
    def test_returns_sections_for_valid_feeds(
        self, mock_parse, mock_fetch_url, mock_extract, local_config
    ):
        """fetch_feeds returns a list of non-empty Section objects."""
        entries = [_make_feed_entry(title=f"Art {i}") for i in range(3)]
        mock_parse.return_value = _make_parsed_feed(entries=entries)

        sections = fetch_feeds(local_config)
        assert len(sections) == 1
        assert sections[0].name == "Test Feed"
        assert len(sections[0].articles) == 3

    @patch("paper_boy.feeds.trafilatura.extract", return_value=None)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value=None)
    @patch("paper_boy.feeds.feedparser.parse")
    def test_skips_empty_sections(self, mock_parse, mock_fetch, mock_ext, local_config):
        """Sections with no extractable articles are excluded from the result."""
        mock_parse.return_value = _make_parsed_feed(
            entries=[_make_feed_entry(summary="short")]
        )

        sections = fetch_feeds(local_config)
        assert len(sections) == 0

    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>Content.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    @patch("paper_boy.feeds.feedparser.parse")
    def test_handles_multiple_feeds(self, mock_parse, mock_fetch, mock_ext, make_config):
        """Each feed config produces a separate section."""
        from paper_boy.config import FeedConfig

        config = make_config(
            feeds=[
                FeedConfig(name="Feed A", url="https://a.com/rss"),
                FeedConfig(name="Feed B", url="https://b.com/rss"),
            ]
        )
        mock_parse.return_value = _make_parsed_feed(entries=[_make_feed_entry()])

        sections = fetch_feeds(config)
        assert len(sections) == 2
        assert sections[0].name == "Feed A"
        assert sections[1].name == "Feed B"

    @patch("paper_boy.feeds.feedparser.parse")
    def test_graceful_degradation_on_feed_failure(self, mock_parse, local_config):
        """A failing feed does not raise — returns no sections."""
        mock_parse.return_value = _make_parsed_feed(
            entries=[], bozo=True, bozo_exception=Exception("bad xml")
        )

        sections = fetch_feeds(local_config)
        assert len(sections) == 0

    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>Content.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    @patch("paper_boy.feeds.feedparser.parse")
    def test_respects_max_articles_per_feed(
        self, mock_parse, mock_fetch, mock_ext, make_config
    ):
        """Only max_articles_per_feed entries are processed."""
        config = make_config(max_articles_per_feed=2)
        entries = [_make_feed_entry(title=f"Art {i}") for i in range(5)]
        mock_parse.return_value = _make_parsed_feed(entries=entries)

        sections = fetch_feeds(config)
        assert len(sections[0].articles) <= 2


# --- TestExtractArticle ---


class TestExtractArticle:
    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>Full article.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html>page</html>")
    def test_returns_article_with_trafilatura_content(
        self, mock_fetch, mock_extract, local_config
    ):
        """Successful trafilatura extraction populates html_content."""
        entry = _make_feed_entry()
        article = _extract_article(entry, local_config)
        assert article is not None
        assert "<p>Full article.</p>" in article.html_content

    @patch("paper_boy.feeds.trafilatura.extract", return_value=None)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value=None)
    def test_falls_back_to_rss_content(self, mock_fetch, mock_extract, local_config):
        """When trafilatura fails, RSS entry content field is used."""
        entry = _make_feed_entry(
            content=[{"value": "<p>RSS content here.</p>"}]
        )
        article = _extract_article(entry, local_config)
        assert article is not None
        assert "RSS content here" in article.html_content

    @patch("paper_boy.feeds.trafilatura.extract", return_value=None)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value=None)
    def test_falls_back_to_rss_summary(self, mock_fetch, mock_extract, local_config):
        """When trafilatura and content fail, a long summary is used."""
        long_summary = "A" * 150
        entry = _make_feed_entry(summary=long_summary)
        article = _extract_article(entry, local_config)
        assert article is not None
        assert article.html_content == long_summary

    @patch("paper_boy.feeds.trafilatura.extract", return_value=None)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value=None)
    def test_returns_none_when_no_url(self, mock_fetch, mock_extract, local_config):
        """Entry with no 'link' returns None."""
        entry = _make_feed_entry(link="")
        article = _extract_article(entry, local_config)
        assert article is None

    @patch("paper_boy.feeds.trafilatura.extract", return_value=None)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value=None)
    def test_returns_none_when_no_content(self, mock_fetch, mock_extract, local_config):
        """Entry with no extractable content returns None."""
        entry = _make_feed_entry(summary="short")
        article = _extract_article(entry, local_config)
        assert article is None

    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>Text.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_extracts_author_from_entry(self, mock_fetch, mock_extract, local_config):
        """Author field is extracted from entry.author."""
        entry = _make_feed_entry(author="Jane Doe")
        article = _extract_article(entry, local_config)
        assert article.author == "Jane Doe"

    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>Text.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_extracts_author_from_authors_list(
        self, mock_fetch, mock_extract, local_config
    ):
        """When entry.author is absent, falls back to entry.authors[0].name."""
        entry = _make_feed_entry(authors=[{"name": "John Smith"}])
        article = _extract_article(entry, local_config)
        assert article.author == "John Smith"

    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>Text.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_extracts_date_from_published(self, mock_fetch, mock_extract, local_config):
        """entry.published is used as article date."""
        entry = _make_feed_entry(published="Mon, 01 Mar 2026 06:00:00 UTC")
        article = _extract_article(entry, local_config)
        assert article.date == "Mon, 01 Mar 2026 06:00:00 UTC"

    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>Text.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_extracts_date_from_updated(self, mock_fetch, mock_extract, local_config):
        """When published is absent, entry.updated is used."""
        entry = _make_feed_entry(updated="2026-03-01T06:00:00Z")
        article = _extract_article(entry, local_config)
        assert article.date == "2026-03-01T06:00:00Z"

    @patch("paper_boy.feeds._process_article_images")
    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>With images.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_processes_images_when_enabled(
        self, mock_fetch, mock_extract, mock_process, make_config
    ):
        """With include_images=True, _process_article_images is called."""
        mock_process.return_value = ("<p>With images.</p>", [])
        config = make_config(include_images=True)
        entry = _make_feed_entry()
        _extract_article(entry, config)
        mock_process.assert_called_once()

    @patch("paper_boy.feeds._process_article_images")
    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>No images.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_skips_images_when_disabled(
        self, mock_fetch, mock_extract, mock_process, make_config
    ):
        """With include_images=False, _process_article_images is NOT called."""
        config = make_config(include_images=False)
        entry = _make_feed_entry()
        article = _extract_article(entry, config)
        mock_process.assert_not_called()
        assert article.images == []

    @patch("paper_boy.feeds.trafilatura.extract", side_effect=Exception("boom"))
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_handles_trafilatura_exception(
        self, mock_fetch, mock_extract, local_config
    ):
        """trafilatura exception is caught; falls back to RSS content."""
        entry = _make_feed_entry(
            content=[{"value": "<p>Fallback content.</p>"}]
        )
        article = _extract_article(entry, local_config)
        assert article is not None
        assert "Fallback content" in article.html_content


# --- TestGetFeedContent ---


class TestGetFeedContent:
    def test_returns_content_value(self):
        """Entry with content[].value returns that value."""
        entry = {"content": [{"value": "<p>Full content.</p>"}]}
        assert _get_feed_content(entry) == "<p>Full content.</p>"

    def test_returns_long_summary(self):
        """Entry with summary > 100 chars returns summary."""
        long_summary = "A" * 150
        entry = {"summary": long_summary}
        assert _get_feed_content(entry) == long_summary

    def test_returns_none_for_short_summary(self):
        """Entry with summary <= 100 chars returns None."""
        entry = {"summary": "Short text."}
        assert _get_feed_content(entry) is None

    def test_returns_none_for_empty_entry(self):
        """Entry with no content and no summary returns None."""
        assert _get_feed_content({}) is None


# --- TestDownloadImage ---


class TestDownloadImage:
    @patch("paper_boy.feeds.urllib.request.urlopen")
    def test_returns_bytes_on_success(self, mock_urlopen):
        """Successful download returns image bytes."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"fake image data"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = _download_image("https://example.com/img.jpg")
        assert result == b"fake image data"

    @patch("paper_boy.feeds.urllib.request.urlopen", side_effect=TimeoutError)
    def test_returns_none_on_timeout(self, mock_urlopen):
        """Timeout exception returns None."""
        assert _download_image("https://example.com/img.jpg") is None

    @patch("paper_boy.feeds.urllib.request.urlopen", side_effect=OSError("HTTP Error"))
    def test_returns_none_on_http_error(self, mock_urlopen):
        """HTTP error returns None."""
        assert _download_image("https://example.com/img.jpg") is None

    @patch("paper_boy.feeds.urllib.request.urlopen")
    def test_sends_user_agent_header(self, mock_urlopen):
        """Request includes PaperBoy user agent."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"data"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        _download_image("https://example.com/img.jpg")

        req = mock_urlopen.call_args[0][0]
        assert "PaperBoy" in req.get_header("User-agent")

    @patch("paper_boy.feeds.urllib.request.urlopen")
    def test_respects_timeout_parameter(self, mock_urlopen):
        """urlopen is called with the given timeout."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"data"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        _download_image("https://example.com/img.jpg", timeout=5)

        assert mock_urlopen.call_args[1]["timeout"] == 5


# --- TestShouldSkipImage (supplementary to test_images.py) ---


class TestShouldSkipImageFeeds:
    @pytest.mark.parametrize(
        "url",
        [
            "https://ads.example.com/banner.jpg",
            "https://cdn.doubleclick.net/pixel.gif",
            "https://pixel.tracker.com/1x1.png",
            "https://analytics.site.com/track.gif",
        ],
    )
    def test_skips_ad_domains(self, url):
        """Ad domain URLs are filtered out."""
        assert _should_skip_image(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://cdn.example.com/images/logo.png",
            "https://cdn.example.com/icon-share.svg",
            "https://example.com/social-icon.png",
        ],
    )
    def test_skips_logo_and_icon_patterns(self, url):
        """Logo and icon path patterns are filtered out."""
        assert _should_skip_image(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://cdn.example.com/article/hero.jpg",
            "https://images.example.com/2026/photo.jpg",
        ],
    )
    def test_allows_normal_images(self, url):
        """Normal article image URLs pass through."""
        assert _should_skip_image(url) is False


# --- TestFetchFeedsWithCache ---


class TestFetchFeedsWithCache:
    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>Content.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    @patch("paper_boy.feeds.feedparser.parse")
    def test_cache_prevents_duplicate_feed_parse(
        self, mock_parse, mock_fetch_url, mock_extract, local_config
    ):
        """Second call with same feed URL uses cache, feedparser.parse called once."""
        entries = [_make_feed_entry()]
        mock_parse.return_value = _make_parsed_feed(entries=entries)

        cache = ContentCache()
        feed_cfg = local_config.feeds[0]

        _fetch_single_feed(feed_cfg, local_config, cache=cache)
        _fetch_single_feed(feed_cfg, local_config, cache=cache)

        mock_parse.assert_called_once()
        assert cache.stats.feed_hits == 1
        assert cache.stats.feed_misses == 1

    @patch("paper_boy.feeds.trafilatura.extract", return_value="<p>Content.</p>")
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_cache_prevents_duplicate_article_extraction(
        self, mock_fetch_url, mock_extract, local_config
    ):
        """Second call with same article URL uses cache, trafilatura called once."""
        cache = ContentCache()
        entry = _make_feed_entry()

        _extract_article(entry, local_config, cache=cache)
        _extract_article(entry, local_config, cache=cache)

        mock_fetch_url.assert_called_once()
        assert cache.stats.article_hits == 1
        assert cache.stats.article_misses == 1

    @patch("paper_boy.feeds.urllib.request.urlopen")
    def test_cache_prevents_duplicate_image_download(self, mock_urlopen):
        """Second call with same image URL uses cache, urlopen called once."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"image data"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        cache = ContentCache()

        result1 = _download_image("https://example.com/img.jpg", cache=cache)
        result2 = _download_image("https://example.com/img.jpg", cache=cache)

        mock_urlopen.assert_called_once()
        assert result1 == b"image data"
        assert result2 == b"image data"
        assert cache.stats.image_hits == 1
        assert cache.stats.image_misses == 1

    @patch("paper_boy.feeds.trafilatura.extract")
    @patch("paper_boy.feeds.trafilatura.fetch_url")
    def test_cached_failure_prevents_retry(
        self, mock_fetch_url, mock_extract, local_config
    ):
        """Cached None (failed extraction) prevents re-calling trafilatura."""
        mock_fetch_url.return_value = None
        mock_extract.return_value = None

        cache = ContentCache()
        entry = _make_feed_entry(summary="short")  # No fallback content either

        _extract_article(entry, local_config, cache=cache)
        _extract_article(entry, local_config, cache=cache)

        # trafilatura.fetch_url called only once — second time served from cache
        mock_fetch_url.assert_called_once()
        assert cache.stats.article_hits == 1
