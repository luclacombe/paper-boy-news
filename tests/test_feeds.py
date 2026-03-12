"""Tests for RSS feed fetching and article extraction."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from paper_boy.cache import ContentCache
from paper_boy import feeds
from paper_boy.feeds import (
    _MAX_CONSECUTIVE_FAILURES,
    Article,
    _count_words,
    _dedup_consecutive_paragraphs,
    _domain_failures,
    _domain_is_blocked,
    _downgrade_body_headings,
    _download_image,
    _extract_article,
    _extract_article_content,
    _extract_bloomberg_article,
    _fetch_bloomberg_section_stories,
    _fetch_bloomberg_bw_stories,
    _extract_from_json_ld,
    _extract_paginated_content,
    _has_paywall_markers,
    _extract_via_archive,
    _fetch_single_feed,
    _get_feed_content,
    _is_premium_title,
    _normalize_html,
    _record_domain_failure,
    _reset_domain_failures,
    _should_skip_image,
    _strip_duplicate_title,
    apply_article_budget,
    fetch_feeds,
)


# --- Helpers ---

# Content long enough to pass the 200-word quality gate in filters.py
_LONG_CONTENT = "<p>" + " ".join(["word"] * 250) + "</p>"


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
    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
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

    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
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

    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    @patch("paper_boy.feeds.feedparser.parse")
    def test_respects_total_article_budget(
        self, mock_parse, mock_fetch, mock_ext, make_config
    ):
        """Total article budget limits output across all feeds."""
        config = make_config(total_article_budget=2)
        entries = [_make_feed_entry(title=f"Art {i}") for i in range(5)]
        mock_parse.return_value = _make_parsed_feed(entries=entries)

        sections = fetch_feeds(config)
        total = sum(len(s.articles) for s in sections)
        assert total <= 2


# --- TestExtractArticle ---


class TestExtractArticle:
    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html>page</html>")
    def test_returns_article_with_trafilatura_content(
        self, mock_fetch, mock_extract, local_config
    ):
        """Successful trafilatura extraction populates html_content."""
        entry = _make_feed_entry()
        article = _extract_article(entry, local_config)
        assert article is not None
        assert "word" in article.html_content

    @patch("paper_boy.feeds.trafilatura.extract", return_value=None)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value=None)
    def test_falls_back_to_rss_content(self, mock_fetch, mock_extract, local_config):
        """When trafilatura fails, RSS entry content field is used."""
        rss_content = "<p>" + " ".join(["rss"] * 250) + "</p>"
        entry = _make_feed_entry(
            content=[{"value": rss_content}]
        )
        article = _extract_article(entry, local_config)
        assert article is not None
        assert "rss" in article.html_content

    @patch("paper_boy.feeds.trafilatura.extract", return_value=None)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value=None)
    def test_falls_back_to_rss_summary(self, mock_fetch, mock_extract, local_config):
        """When trafilatura and content fail, a long summary is used."""
        long_summary = " ".join(["summary"] * 250)
        entry = _make_feed_entry(summary=long_summary)
        article = _extract_article(entry, local_config)
        assert article is not None
        assert "summary" in article.html_content

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

    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_extracts_author_from_entry(self, mock_fetch, mock_extract, local_config):
        """Author field is extracted from entry.author."""
        entry = _make_feed_entry(author="Jane Doe")
        article = _extract_article(entry, local_config)
        assert article.author == "Jane Doe"

    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_extracts_author_from_authors_list(
        self, mock_fetch, mock_extract, local_config
    ):
        """When entry.author is absent, falls back to entry.authors[0].name."""
        entry = _make_feed_entry(authors=[{"name": "John Smith"}])
        article = _extract_article(entry, local_config)
        assert article.author == "John Smith"

    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_extracts_date_from_published(self, mock_fetch, mock_extract, local_config):
        """entry.published is used as article date."""
        entry = _make_feed_entry(published="Mon, 01 Mar 2026 06:00:00 UTC")
        article = _extract_article(entry, local_config)
        assert article.date == "Mon, 01 Mar 2026 06:00:00 UTC"

    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_extracts_date_from_updated(self, mock_fetch, mock_extract, local_config):
        """When published is absent, entry.updated is used."""
        entry = _make_feed_entry(updated="2026-03-01T06:00:00Z")
        article = _extract_article(entry, local_config)
        assert article.date == "2026-03-01T06:00:00Z"

    @patch("paper_boy.feeds._process_article_images")
    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html></html>")
    def test_processes_images_when_enabled(
        self, mock_fetch, mock_extract, mock_process, make_config
    ):
        """With include_images=True, _process_article_images is called."""
        mock_process.return_value = (_LONG_CONTENT, [])
        config = make_config(include_images=True)
        entry = _make_feed_entry()
        _extract_article(entry, config)
        mock_process.assert_called_once()

    @patch("paper_boy.feeds._process_article_images")
    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
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
        rss_content = "<p>" + " ".join(["fallback"] * 250) + "</p>"
        entry = _make_feed_entry(
            content=[{"value": rss_content}]
        )
        article = _extract_article(entry, local_config)
        assert article is not None
        assert "fallback" in article.html_content


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
    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
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

    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
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


# --- TestCountWords ---


class TestCountWords:
    def test_counts_words_in_plain_text(self):
        assert _count_words("hello world foo bar") == 4

    def test_counts_words_stripping_html(self):
        assert _count_words("<p>Hello <b>world</b> here.</p>") == 3

    def test_empty_string(self):
        assert _count_words("") == 0

    def test_only_tags(self):
        assert _count_words("<p></p><div></div>") == 0


# --- TestExtractArticleContent ---


class TestExtractArticleContent:
    def setup_method(self):
        _reset_domain_failures()

    @patch("paper_boy.feeds._fetch_page", return_value=None)
    @patch("paper_boy.feeds._trafilatura_extract")
    def test_returns_strategy1_when_sufficient(self, mock_traf, mock_fetch):
        """Strategy 1 (standard trafilatura) succeeds with enough words."""
        long_html = "<p>" + " ".join(["word"] * 200) + "</p>"
        mock_traf.return_value = long_html

        result = _extract_article_content("https://example.com/article", True)
        assert result is not None
        assert "word" in result
        # Should not attempt bot UA fetch
        mock_fetch.assert_not_called()

    @patch("paper_boy.feeds._extract_via_archive", return_value=None)
    @patch("paper_boy.feeds._extract_from_json_ld", return_value=None)
    @patch("paper_boy.feeds._trafilatura_extract_from_html")
    @patch("paper_boy.feeds._fetch_page")
    @patch("paper_boy.feeds._trafilatura_extract")
    def test_falls_back_to_bot_ua(
        self, mock_traf, mock_fetch, mock_traf_html, mock_json_ld, mock_archive
    ):
        """Strategy 2 fires when strategy 1 and 1.5 (browser UA) fail."""
        mock_traf.return_value = "<p>Short paywall text.</p>"  # < 150 words
        long_html = "<p>" + " ".join(["word"] * 200) + "</p>"
        # browser UA returns None, bot UA returns full page
        mock_fetch.side_effect = [None, "<html>full page</html>"]
        mock_traf_html.return_value = long_html

        result = _extract_article_content("https://example.com/paywalled", True)
        assert result is not None
        assert "word" in result
        assert mock_fetch.call_count == 2

    @patch("paper_boy.feeds._extract_via_archive", return_value=None)
    @patch("paper_boy.feeds._extract_from_json_ld", return_value=None)
    @patch("paper_boy.feeds._trafilatura_extract_from_html")
    @patch("paper_boy.feeds._fetch_page")
    @patch("paper_boy.feeds._trafilatura_extract")
    def test_paywall_teaser_falls_through_to_bot_ua(
        self, mock_traf, mock_fetch, mock_traf_html, mock_json_ld, mock_archive
    ):
        """S1 paywall teaser (enough words but paywall phrases) falls through to S2.

        FT pattern: S1 extracts ~170 words of 'Subscribe to unlock this article'
        paywall text which passes MIN_ARTICLE_WORDS but contains paywall markers.
        The pipeline should NOT accept this and should continue to S2 (bot UA).
        """
        paywall_teaser = (
            "<p>Subscribe to unlock this article</p>"
            "<p>Try unlimited access Only €1 for 4 weeks Then €69 per month.</p>"
            "<p>" + " ".join(["teaser"] * 160) + "</p>"
        )
        full_article = "<p>" + " ".join(["article"] * 500) + "</p>"
        mock_traf.return_value = paywall_teaser
        # browser UA returns same paywall, bot UA returns full page
        mock_fetch.side_effect = [
            "<html>paywall page</html>",
            "<html>full page</html>",
        ]
        mock_traf_html.side_effect = [paywall_teaser, full_article]

        result = _extract_article_content("https://www.ft.com/content/abc123", True)
        assert result is not None
        assert "article" in result
        assert "Subscribe to unlock" not in result
        # Both browser UA and bot UA fetches should have been attempted
        assert mock_fetch.call_count == 2

    @patch("paper_boy.feeds._extract_via_archive", return_value=None)
    @patch("paper_boy.feeds._trafilatura_extract_from_html", return_value=None)
    @patch("paper_boy.feeds._fetch_page")
    @patch("paper_boy.feeds._trafilatura_extract", return_value=None)
    def test_falls_back_to_json_ld(self, mock_traf, mock_fetch, mock_traf_html, mock_archive):
        """Strategy 3 (JSON-LD) fires when strategies 1, 1.5, and 2 fail."""
        body_text = " ".join(["word"] * 200)
        page_html = (
            '<html><head><script type="application/ld+json">'
            + '{"@type":"Article","articleBody":"' + body_text + '"}'
            + "</script></head></html>"
        )
        # browser UA returns None, bot UA returns page with JSON-LD
        mock_fetch.side_effect = [None, page_html]

        result = _extract_article_content("https://example.com/paywalled", False)
        assert result is not None
        assert "word" in result

    @patch("paper_boy.feeds._extract_via_archive", return_value=None)
    @patch("paper_boy.feeds._fetch_page", return_value=None)
    @patch("paper_boy.feeds._trafilatura_extract", return_value=None)
    def test_returns_none_when_all_strategies_fail(self, mock_traf, mock_fetch, mock_archive):
        """Returns None when no strategy produces content."""
        result = _extract_article_content("https://example.com/broken", True)
        assert result is None

    @patch("paper_boy.feeds._extract_via_archive", return_value=None)
    @patch("paper_boy.feeds._fetch_page", return_value=None)
    @patch("paper_boy.feeds._trafilatura_extract")
    def test_returns_short_result_normalized_when_no_better(
        self, mock_traf, mock_fetch, mock_archive
    ):
        """Short result from strategy 1 is returned (normalized) if no other succeeds."""
        mock_traf.return_value = '<p style="color:red">Short but real.</p>'

        result = _extract_article_content("https://example.com/short", True)
        assert result is not None
        assert "Short but real." in result
        # Inline style should be stripped by normalization
        assert 'style="' not in result


# --- TestExtractFromJsonLd ---


class TestExtractFromJsonLd:
    def test_extracts_article_body(self):
        body = " ".join(["word"] * 200)
        html = (
            '<script type="application/ld+json">'
            '{"@type":"NewsArticle","articleBody":"' + body + '"}'
            "</script>"
        )
        result = _extract_from_json_ld(html)
        assert result is not None
        assert "<p>" in result
        assert "word" in result

    def test_extracts_from_graph_array(self):
        body = " ".join(["word"] * 200)
        html = (
            '<script type="application/ld+json">'
            '{"@graph":[{"@type":"Article","articleBody":"' + body + '"}]}'
            "</script>"
        )
        result = _extract_from_json_ld(html)
        assert result is not None

    def test_extracts_text_field(self):
        """Falls back to 'text' field when 'articleBody' is absent."""
        body = " ".join(["word"] * 200)
        html = (
            '<script type="application/ld+json">'
            '{"@type":"Article","text":"' + body + '"}'
            "</script>"
        )
        result = _extract_from_json_ld(html)
        assert result is not None

    def test_returns_none_for_no_json_ld(self):
        assert _extract_from_json_ld("<html><body>No JSON-LD</body></html>") is None

    def test_returns_none_for_invalid_json(self):
        html = '<script type="application/ld+json">{invalid json}</script>'
        assert _extract_from_json_ld(html) is None

    def test_returns_none_for_short_body(self):
        html = (
            '<script type="application/ld+json">'
            '{"@type":"Article","articleBody":"Too short."}'
            "</script>"
        )
        assert _extract_from_json_ld(html) is None

    def test_splits_paragraphs_on_double_newline(self):
        body = "First paragraph.\\n\\nSecond paragraph.\\n\\nThird paragraph."
        # Make it long enough (>100 chars)
        body = body + " " + " ".join(["padding"] * 20)
        html = (
            '<script type="application/ld+json">'
            '{"@type":"Article","articleBody":"' + body + '"}'
            "</script>"
        )
        result = _extract_from_json_ld(html)
        assert result is not None
        assert result.count("<p>") >= 1

    def test_handles_list_format(self):
        body = " ".join(["word"] * 200)
        html = (
            '<script type="application/ld+json">'
            '[{"@type":"Article","articleBody":"' + body + '"}]'
            "</script>"
        )
        result = _extract_from_json_ld(html)
        assert result is not None


# --- TestNormalizeHtml ---


class TestNormalizeHtml:
    @pytest.mark.parametrize("input_html,expected", [
        # Empty tag removal
        ("<p></p><p>Real content.</p>", "<p>Real content.</p>"),
        ("<div></div><p>Text.</p>", "<p>Text.</p>"),
        ("<span></span><p>Text.</p>", "<p>Text.</p>"),
        # Inline style stripping
        ('<p style="color:red; font-size:14px">Hello</p>', "<p>Hello</p>"),
        # Whitespace stripping
        ("  <p>Text.</p>  ", "<p>Text.</p>"),
        # Clean passthrough
        ("<p>Already clean content.</p>", "<p>Already clean content.</p>"),
        # Zero-width character stripping
        ("<p>Hello\u200bworld</p>", "<p>Helloworld</p>"),
        ("<p>Test\u200c\u2060text</p>", "<p>Testtext</p>"),
        ("<p>BOM\ufeffhere</p>", "<p>BOMhere</p>"),
        # Self-closing empty tags
        ("<p/><p>Text.</p>", "<p>Text.</p>"),
        ("<div/><p>Text.</p>", "<p>Text.</p>"),
        # TEI table conversion
        ("<row><cell>Data</cell></row>", "<tr><td>Data</td></tr>"),
    ])
    def test_normalize_exact(self, input_html, expected):
        assert _normalize_html(input_html) == expected

    @pytest.mark.parametrize("artifact", [
        "hide caption",
        "toggle caption",
        "Enlarge this image",
    ])
    def test_removes_caption_artifacts(self, artifact):
        result = _normalize_html(f"<p>{artifact}</p>")
        assert artifact.lower() not in result.lower()

    def test_strips_html_body_wrapper(self):
        html = '<html>\n  <body>\n    <h1>Title</h1>\n    <p>Content.</p>\n  </body>\n</html>'
        result = _normalize_html(html)
        assert "<html>" not in result
        assert "<body>" not in result
        assert "</html>" not in result
        assert "</body>" not in result
        assert "<h1>Title</h1>" in result
        assert "<p>Content.</p>" in result

    def test_flattens_nested_figure(self):
        html = '<figure><figure><img src="x.jpg"/></figure><figcaption>Caption</figcaption></figure>'
        result = _normalize_html(html)
        assert "<figure><figure>" not in result
        assert "<img" in result
        assert "Caption" in result

    def test_removes_cms_alt_figcaption(self):
        html = '<figure><img src="x.jpg"/><figcaption>Image may contain Person Standing</figcaption></figure>'
        result = _normalize_html(html)
        assert "Image may contain" not in result
        assert "<img" in result


# --- TestDedupConsecutiveParagraphs ---


class TestDedupConsecutiveParagraphs:
    def test_removes_consecutive_duplicate_p(self):
        html = "<p>Same text.</p><p>Same text.</p><p>Different.</p>"
        result = _dedup_consecutive_paragraphs(html)
        assert result.count("Same text.") == 1
        assert "Different." in result

    def test_removes_consecutive_duplicate_heading(self):
        html = "<h2>Title</h2><h2>Title</h2><p>Content.</p>"
        result = _dedup_consecutive_paragraphs(html)
        assert result.count("Title") == 1

    def test_preserves_non_consecutive_duplicates(self):
        html = "<p>Text A.</p><p>Text B.</p><p>Text A.</p>"
        result = _dedup_consecutive_paragraphs(html)
        assert result.count("Text A.") == 2

    def test_passthrough_no_duplicates(self):
        html = "<p>First.</p><p>Second.</p><p>Third.</p>"
        result = _dedup_consecutive_paragraphs(html)
        assert result == html

    def test_handles_inner_tags(self):
        html = "<p><strong>Bold</strong> text.</p><p><strong>Bold</strong> text.</p>"
        result = _dedup_consecutive_paragraphs(html)
        assert result.count("Bold") == 1

    def test_dedup_across_figure(self):
        """Verge pattern: subtitle duplicated with a <figure> in between."""
        html = (
            "<h2>Title</h2><p>Subtitle.</p>"
            '<figure><img src="x.jpg"/></figure>'
            "<h2>Title</h2><p>Subtitle.</p>"
            "<p>Body text.</p>"
        )
        result = _dedup_consecutive_paragraphs(html)
        assert result.count("Title") == 1
        assert result.count("Subtitle.") == 1
        assert "Body text." in result


# --- TestVideoUrlFilter ---


class TestVideoUrlFilter:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.aljazeera.com/video/2026/3/8/some-video",
            "https://www.aljazeera.com/program/talk-to-al-jazeera/2026/3/8/ep",
            "https://example.com/podcasts/episode-42",
            "https://example.com/live/breaking-news",
        ],
    )
    @patch("paper_boy.feeds._extract_article_content", return_value=_LONG_CONTENT)
    def test_skips_non_article_urls(self, mock_extract, url, local_config):
        """Non-article URLs (video, program, podcasts, live) are skipped."""
        entry = _make_feed_entry(link=url)
        article = _extract_article(entry, local_config)
        assert article is None
        mock_extract.assert_not_called()

    @patch("paper_boy.feeds._extract_article_content", return_value=_LONG_CONTENT)
    def test_allows_normal_article_urls(self, mock_extract, local_config):
        """Normal article URLs are not filtered."""
        entry = _make_feed_entry(
            link="https://www.aljazeera.com/news/2026/3/8/article"
        )
        article = _extract_article(entry, local_config)
        assert article is not None


# --- TestStripDuplicateTitle ---


class TestStripDuplicateTitle:
    def test_removes_exact_match_h1(self):
        """Leading <h1> that exactly matches the title is removed."""
        html = "<h1>Breaking News Today</h1><p>Article body here.</p>"
        result = _strip_duplicate_title(html, "Breaking News Today")
        assert "<h1>" not in result
        assert "<p>Article body here.</p>" in result

    def test_removes_exact_match_h2(self):
        """Leading <h2> matching the title is also removed."""
        html = "<h2>Breaking News Today</h2><p>Article body here.</p>"
        result = _strip_duplicate_title(html, "Breaking News Today")
        assert "<h2>" not in result
        assert "<p>Article body here.</p>" in result

    def test_case_insensitive_match(self):
        """Matching is case-insensitive."""
        html = "<h1>BREAKING NEWS TODAY</h1><p>Body.</p>"
        result = _strip_duplicate_title(html, "Breaking News Today")
        assert "<h1>" not in result

    def test_strips_punctuation_for_match(self):
        """Punctuation differences don't prevent matching."""
        html = '<h1>"Breaking News" Today!</h1><p>Body.</p>'
        result = _strip_duplicate_title(html, "Breaking News Today")
        assert "<h1>" not in result

    def test_containment_match_heading_in_title(self):
        """Heading text contained in title matches (title may be longer)."""
        html = "<h1>Breaking News</h1><p>Body.</p>"
        result = _strip_duplicate_title(html, "Breaking News: A Major Story")
        assert "<h1>" not in result

    def test_containment_match_title_in_heading(self):
        """Title contained in heading matches (heading may have extra text)."""
        html = "<h1>Breaking News: A Major Story Unfolds</h1><p>Body.</p>"
        result = _strip_duplicate_title(html, "Breaking News")
        assert "<h1>" not in result

    def test_no_match_preserves_heading(self):
        """Non-matching heading is preserved."""
        html = "<h1>Completely Different Heading</h1><p>Body.</p>"
        result = _strip_duplicate_title(html, "Breaking News Today")
        assert "<h1>Completely Different Heading</h1>" in result

    def test_no_heading_returns_unchanged(self):
        """HTML without any heading is returned unchanged."""
        html = "<p>Just a paragraph.</p><p>Another one.</p>"
        result = _strip_duplicate_title(html, "Some Title")
        assert result == html

    def test_non_leading_heading_preserved(self):
        """Only the FIRST heading is checked — later headings are preserved."""
        html = "<p>Intro.</p><h1>Breaking News Today</h1><p>Body.</p>"
        result = _strip_duplicate_title(html, "Breaking News Today")
        assert "<h1>Breaking News Today</h1>" in result

    def test_heading_with_inner_tags(self):
        """Heading containing inline HTML (e.g. <em>) still matches."""
        html = "<h1><em>Breaking</em> News Today</h1><p>Body.</p>"
        result = _strip_duplicate_title(html, "Breaking News Today")
        assert "<h1>" not in result

    def test_whitespace_around_heading(self):
        """Leading whitespace before the heading doesn't prevent matching."""
        html = "  \n  <h1>Breaking News</h1><p>Body.</p>"
        result = _strip_duplicate_title(html, "Breaking News")
        assert "<h1>" not in result

    def test_empty_html(self):
        """Empty HTML returns empty string."""
        result = _strip_duplicate_title("", "Some Title")
        assert result == ""

    def test_empty_title(self):
        """Empty title doesn't remove any heading."""
        html = "<h1>Some Heading</h1><p>Body.</p>"
        result = _strip_duplicate_title(html, "")
        assert "<h1>Some Heading</h1>" in result


# --- TestStripDuplicateTitleIntegration ---


class TestStripDuplicateTitleIntegration:
    @patch(
        "paper_boy.feeds._extract_article_content",
        return_value="<h1>Test Article</h1>" + _LONG_CONTENT,
    )
    def test_extract_article_strips_duplicate_title(self, mock_extract, local_config):
        """_extract_article removes duplicate <h1> matching the entry title."""
        entry = _make_feed_entry(title="Test Article")
        article = _extract_article(entry, local_config)
        assert article is not None
        assert "<h1>" not in article.html_content
        assert "word" in article.html_content

    @patch(
        "paper_boy.feeds._extract_article_content",
        return_value="<h1>Different Heading</h1>" + _LONG_CONTENT,
    )
    def test_extract_article_downgrades_non_matching_heading(
        self, mock_extract, local_config
    ):
        """Non-matching <h1> is downgraded to <h2> (epub.py owns the <h1>)."""
        entry = _make_feed_entry(title="Test Article")
        article = _extract_article(entry, local_config)
        assert article is not None
        assert "<h2>Different Heading</h2>" in article.html_content
        assert "<h1>" not in article.html_content


# --- TestBrowserUAFallback ---


class TestBrowserUAFallback:
    @patch("paper_boy.feeds._extract_via_archive", return_value=None)
    @patch("paper_boy.feeds._trafilatura_extract_from_html")
    @patch("paper_boy.feeds._fetch_page")
    @patch("paper_boy.feeds._trafilatura_extract")
    def test_falls_back_to_browser_ua(
        self, mock_traf, mock_fetch, mock_traf_html, mock_archive
    ):
        """Strategy 1.5 (browser UA) fires when strategy 1 returns short content."""
        mock_traf.return_value = "<p>Short paywall text.</p>"  # < 150 words
        long_html = "<p>" + " ".join(["word"] * 200) + "</p>"
        mock_fetch.return_value = "<html>browser page</html>"
        mock_traf_html.return_value = long_html

        result = _extract_article_content("https://nature.com/articles/123", True)
        assert result is not None
        assert "word" in result
        # _fetch_page called once with browser UA
        mock_fetch.assert_called_once()


# --- TestBloombergExtraction ---


class TestBloombergExtraction:
    @patch("paper_boy.feeds._fetch_bloomberg_api")
    def test_bloomberg_api_success(self, mock_api):
        """Bloomberg BW news API returns article HTML and byline."""
        body = "<p>" + " ".join(["word"] * 200) + "</p>"
        mock_api.return_value = {"html": body, "byline": "Test Author"}

        html, byline = _extract_bloomberg_article("TEST_ID_123")
        assert html is not None
        assert "word" in html
        assert byline == "Test Author"

    @patch("paper_boy.feeds._fetch_bloomberg_api")
    def test_bloomberg_api_no_data(self, mock_api):
        """API returning None gives (None, None)."""
        mock_api.return_value = None
        html, byline = _extract_bloomberg_article("TEST_ID_123")
        assert html is None
        assert byline is None

    @patch("paper_boy.feeds._fetch_bloomberg_api")
    def test_bloomberg_api_short_body(self, mock_api):
        """HTML < MIN_ARTICLE_WORDS returns None for html."""
        mock_api.return_value = {"html": "<p>Too short.</p>", "byline": "Author"}
        html, byline = _extract_bloomberg_article("TEST_ID_123")
        assert html is None

    @patch("paper_boy.feeds._fetch_bloomberg_api")
    def test_bloomberg_section_stories(self, mock_api):
        """Section listing extracts deduplicated stories."""
        mock_api.side_effect = [
            # Nav API response
            {"searchNav": [{"items": [
                {"id": "tech", "title": "Tech", "links": {"self": {"href": "/wssmobile/v1/pages/business/phx-tech"}}}
            ]}]},
            # Section listing response
            {"modules": [
                {"stories": [
                    {"type": "article", "internalID": "A1", "title": "Story 1"},
                    {"type": "article", "internalID": "A1", "title": "Story 1 dup"},
                    {"type": "article", "internalID": "A2", "title": "Story 2"},
                    {"type": "video", "internalID": "V1", "title": "Video"},
                ]},
            ]},
        ]
        stories = _fetch_bloomberg_section_stories("tech")
        assert len(stories) == 2
        assert stories[0]["internalID"] == "A1"
        assert stories[1]["internalID"] == "A2"

    @patch("paper_boy.feeds._fetch_bloomberg_api")
    def test_bloomberg_bw_stories(self, mock_api):
        """Businessweek latest issue fetches TOC articles."""
        mock_api.side_effect = [
            # BW list response
            {"magazines": [{"id": "26_03"}]},
            # BW week TOC response
            {"modules": [
                {"articles": [{"id": "BW1", "title": "BW Article 1"}]},
                {"articles": [{"id": "BW2", "title": "BW Article 2"}]},
            ]},
        ]
        stories = _fetch_bloomberg_bw_stories()
        assert len(stories) == 2
        assert stories[0]["id"] == "BW1"


# --- TestArchiveExtraction ---


@patch("paper_boy.feeds._HAS_MODERN_SSL", True)
class TestArchiveExtraction:
    @patch("paper_boy.feeds._trafilatura_extract_from_html")
    @patch("paper_boy.feeds._fetch_page")
    def test_archive_success(self, mock_fetch, mock_traf_html):
        """Archive.today proxy returns extracted content."""
        long_html = "<p>" + " ".join(["word"] * 200) + "</p>"
        mock_fetch.return_value = "<html>archived page</html>"
        mock_traf_html.return_value = long_html

        result = _extract_via_archive("https://example.com/article", True)
        assert result is not None
        assert "word" in result

    @patch("paper_boy.feeds._trafilatura_extract_from_html")
    @patch("paper_boy.feeds._fetch_page")
    def test_archive_tries_multiple_tlds(self, mock_fetch, mock_traf_html):
        """Archive tries all TLDs until one succeeds."""
        mock_fetch.return_value = None
        _extract_via_archive("https://example.com/article", True)
        # Should try all 6 TLDs when all fail
        assert mock_fetch.call_count == len(feeds._ARCHIVE_TLDS)
        # All calls should use /latest/ URL pattern with browser UA
        for call in mock_fetch.call_args_list:
            url, ua = call[0]
            assert "/latest/https://example.com/article" in url
            assert "Mozilla/5.0" in ua

    @patch("paper_boy.feeds._trafilatura_extract_from_html")
    @patch("paper_boy.feeds._fetch_page")
    def test_archive_stops_on_first_success(self, mock_fetch, mock_traf_html):
        """Archive stops trying TLDs once one succeeds."""
        long_html = "<p>" + " ".join(["word"] * 200) + "</p>"
        mock_fetch.return_value = "<html>page</html>"
        mock_traf_html.return_value = long_html
        result = _extract_via_archive("https://example.com/article", True)
        assert result is not None
        # Should stop after first successful TLD
        assert mock_fetch.call_count == 1

    @patch("paper_boy.feeds._trafilatura_extract_from_html")
    @patch("paper_boy.feeds._fetch_page")
    def test_archive_strips_query_params(self, mock_fetch, mock_traf_html):
        """Query parameters are stripped before archive lookup."""
        mock_fetch.return_value = None
        _extract_via_archive("https://example.com/article?param=1&foo=bar", True)
        # All calls should use URL without query params
        for call in mock_fetch.call_args_list:
            url, _ = call[0]
            assert "?param" not in url
            assert "https://example.com/article" in url

    @patch("paper_boy.feeds._fetch_page", return_value=None)
    def test_archive_returns_none_on_failure(self, mock_fetch):
        """Returns None when archive fetch fails."""
        result = _extract_via_archive("https://example.com/article", True)
        assert result is None


class TestProjectSyndicateRouting:
    """Project Syndicate URLs go directly to archive.today."""

    @patch("paper_boy.feeds._extract_via_archive")
    def test_ps_routes_to_archive(self, mock_archive):
        """PS URLs skip normal strategies and go straight to archive."""
        mock_archive.return_value = "<p>full article</p>"
        result = _extract_article_content(
            "https://www.project-syndicate.org/commentary/test-article", True
        )
        mock_archive.assert_called_once_with(
            "https://www.project-syndicate.org/commentary/test-article", True
        )
        assert result is not None

    @patch("paper_boy.feeds._extract_via_archive", return_value=None)
    @patch("paper_boy.feeds._trafilatura_extract")
    def test_ps_does_not_try_normal_strategies(self, mock_traf, mock_archive):
        """PS URLs don't fall through to trafilatura when archive fails."""
        result = _extract_article_content(
            "https://www.project-syndicate.org/commentary/test-article", True
        )
        assert result is None
        mock_traf.assert_not_called()


# --- TestPaginatedExtraction ---


class TestPaginatedExtraction:
    @patch("paper_boy.feeds._trafilatura_extract_from_html")
    @patch("paper_boy.feeds._fetch_page")
    def test_ars_pagination_appends(self, mock_fetch, mock_traf_html):
        """Pagination links are followed and content concatenated."""
        raw_page = '<a href="https://arstechnica.com/article/2/">Page 2</a>'
        page2_content = "<p>" + " ".join(["extra"] * 50) + "</p>"
        mock_fetch.return_value = "<html>page 2</html>"
        mock_traf_html.return_value = page2_content

        result = _extract_paginated_content(
            "https://arstechnica.com/article/", raw_page, True
        )
        assert result is not None
        assert "extra" in result

    def test_ars_pagination_no_links(self):
        """Page without pagination links returns None."""
        raw_page = "<html><p>No pagination here.</p></html>"
        result = _extract_paginated_content(
            "https://arstechnica.com/article/", raw_page, True
        )
        assert result is None

    @patch("paper_boy.feeds._trafilatura_extract_from_html")
    @patch("paper_boy.feeds._fetch_page")
    def test_ars_strips_heading_from_continuation(self, mock_fetch, mock_traf_html):
        """h1/h2 headings are stripped from continuation pages."""
        raw_page = '<a href="https://arstechnica.com/article/2/">Page 2</a>'
        mock_fetch.return_value = "<html>page 2</html>"
        mock_traf_html.return_value = "<h1>Article Title</h1><p>Page 2 content.</p>"

        result = _extract_paginated_content(
            "https://arstechnica.com/article/", raw_page, True
        )
        assert result is not None
        assert "<h1>" not in result
        assert "Page 2 content." in result


# --- TestHNSelfPostHandling ---


class TestHNSelfPostHandling:
    @patch("paper_boy.feeds._extract_article_content")
    def test_hn_self_post_uses_feed_content(self, mock_extract, local_config):
        """HN self-post with news.ycombinator.com/item link uses RSS content."""
        entry = _make_feed_entry(
            title="Ask HN: Something",
            link="https://news.ycombinator.com/item?id=12345",
            content=[{"value": "<p>This is the self-post content.</p>"}],
            author="hackernews_user",
        )
        article = _extract_article(entry, local_config)
        assert article is not None
        assert "self-post content" in article.html_content
        assert article.author == "hackernews_user"
        # Should NOT call _extract_article_content
        mock_extract.assert_not_called()

    def test_hn_self_post_no_content_returns_none(self, local_config):
        """HN self-post with no/short RSS content returns None."""
        entry = _make_feed_entry(
            title="Ask HN: Something",
            link="https://news.ycombinator.com/item?id=12345",
            summary="short",
        )
        article = _extract_article(entry, local_config)
        assert article is None

    @patch("paper_boy.feeds._extract_article_content", return_value=_LONG_CONTENT)
    def test_hn_external_link_normal_extraction(self, mock_extract, local_config):
        """HN entry with external link goes through normal extraction."""
        entry = _make_feed_entry(
            title="Some External Article",
            link="https://example.com/article/123",
        )
        article = _extract_article(entry, local_config)
        mock_extract.assert_called_once()


# --- TestDowngradeBodyHeadings ---


class TestDowngradeBodyHeadings:
    def test_downgrades_h1_to_h2(self):
        """Single <h1> is downgraded to <h2>."""
        html = "<h1>Subheading</h1><p>Body text.</p>"
        result = _downgrade_body_headings(html)
        assert "<h2>Subheading</h2>" in result
        assert "<h1>" not in result

    def test_downgrades_multiple_h1s(self):
        """Multiple <h1> tags are all downgraded."""
        html = "<h1>First</h1><p>Text.</p><h1>Second</h1><p>More.</p>"
        result = _downgrade_body_headings(html)
        assert result.count("<h2") == 2
        assert result.count("</h2>") == 2
        assert "<h1" not in result

    def test_preserves_h2_and_h3(self):
        """Existing <h2> and <h3> tags are not modified."""
        html = "<h2>Existing H2</h2><h3>Existing H3</h3>"
        result = _downgrade_body_headings(html)
        assert result == html

    def test_handles_h1_with_attributes(self):
        """<h1> tags with attributes are downgraded correctly."""
        html = '<h1 class="title" id="main">Heading</h1>'
        result = _downgrade_body_headings(html)
        assert '<h2 class="title" id="main">Heading</h2>' in result
        assert "<h1" not in result

    def test_case_insensitive(self):
        """Handles uppercase <H1> tags."""
        html = "<H1>Heading</H1>"
        result = _downgrade_body_headings(html)
        assert "<h2>Heading</h2>" in result

    def test_no_h1_returns_unchanged(self):
        """HTML without <h1> is returned unchanged."""
        html = "<p>Just a paragraph.</p>"
        result = _downgrade_body_headings(html)
        assert result == html


class TestApplyArticleBudget:
    """Tests for the total article budget distribution."""

    def _make_section(self, name: str, num_articles: int) -> "Section":
        from paper_boy.feeds import Article, Section

        articles = [
            Article(
                title=f"{name} Art {i}",
                url=f"https://example.com/{name}/{i}",
                html_content="<p>Content</p>",
            )
            for i in range(num_articles)
        ]
        return Section(name=name, articles=articles)

    def test_no_trimming_when_under_budget(self):
        """If total articles <= budget, return as-is."""
        sections = [self._make_section("A", 2), self._make_section("B", 3)]
        result = apply_article_budget(sections, 10)
        assert sum(len(s.articles) for s in result) == 5

    def test_no_trimming_when_equal_to_budget(self):
        sections = [self._make_section("A", 3), self._make_section("B", 2)]
        result = apply_article_budget(sections, 5)
        assert sum(len(s.articles) for s in result) == 5

    def test_budget_less_than_sources(self):
        """More sources than budget — first N sources get 1 article each."""
        sections = [self._make_section(f"S{i}", 3) for i in range(5)]
        result = apply_article_budget(sections, 3)
        assert len(result) == 3
        for s in result:
            assert len(s.articles) == 1

    def test_round_robin_distribution(self):
        """Remaining budget distributed across sources."""
        sections = [self._make_section("A", 5), self._make_section("B", 5)]
        result = apply_article_budget(sections, 4)
        total = sum(len(s.articles) for s in result)
        assert total == 4
        # Each source gets at least 1
        for s in result:
            assert len(s.articles) >= 1

    def test_each_source_gets_at_least_one(self):
        """Every source is guaranteed 1 article."""
        sections = [self._make_section(f"S{i}", 3) for i in range(4)]
        result = apply_article_budget(sections, 6)
        assert len(result) == 4
        for s in result:
            assert len(s.articles) >= 1
        assert sum(len(s.articles) for s in result) == 6

    def test_empty_sections(self):
        """Empty input returns empty output."""
        result = apply_article_budget([], 10)
        assert result == []

    def test_respects_available_articles(self):
        """Cannot allocate more than a source has."""
        sections = [self._make_section("A", 1), self._make_section("B", 10)]
        result = apply_article_budget(sections, 8)
        total = sum(len(s.articles) for s in result)
        assert total <= 8
        assert len(result[0].articles) == 1  # A only had 1


# --- Consecutive failure abort ---


class TestPremiumTitleSkipping:
    """Test that entries with premium title prefixes are skipped."""

    def test_stat_plus_detected(self):
        assert _is_premium_title("STAT+: Some premium article") is True

    def test_regular_title_not_detected(self):
        assert _is_premium_title("Fresh turmoil at the FDA") is False

    def test_empty_title(self):
        assert _is_premium_title("") is False

    def test_premium_entries_skipped_in_feed(self, make_config):
        """Premium entries are skipped without counting as consecutive failures."""
        entries = [
            _make_feed_entry(title="STAT+: Premium 1", link="https://example.com/1"),
            _make_feed_entry(title="STAT+: Premium 2", link="https://example.com/2"),
            _make_feed_entry(title="STAT+: Premium 3", link="https://example.com/3"),
            _make_feed_entry(title="STAT+: Premium 4", link="https://example.com/4"),
            _make_feed_entry(title="Free article", link="https://example.com/5"),
        ]
        feed_cfg = MagicMock()
        feed_cfg.name = "TestFeed"
        feed_cfg.url = "https://example.com/feed"
        feed_cfg.category = ""
        config = make_config()

        with (
            patch("paper_boy.feeds.feedparser.parse") as mock_parse,
            patch("paper_boy.feeds._extract_article") as mock_extract,
            patch("paper_boy.feeds.is_safe_url", return_value=True),
        ):
            mock_parse.return_value = _make_parsed_feed(entries=entries)
            mock_extract.return_value = Article(
                title="Free article", url="https://example.com/5",
                html_content=_LONG_CONTENT,
            )

            section = _fetch_single_feed(feed_cfg, config)

            # Only the free article should be attempted
            assert mock_extract.call_count == 1
            assert len(section.articles) == 1


class TestConsecutiveFailureAbort:
    """Test that _fetch_single_feed aborts after consecutive extraction failures."""

    def test_aborts_after_max_consecutive_failures(self, make_config):
        """Feed stops after _MAX_CONSECUTIVE_FAILURES consecutive failures."""
        entries = [
            _make_feed_entry(title=f"Article {i}", link=f"https://example.com/{i}")
            for i in range(10)
        ]
        feed_cfg = MagicMock()
        feed_cfg.name = "TestFeed"
        feed_cfg.url = "https://example.com/feed"
        feed_cfg.category = ""
        config = make_config()

        with (
            patch("paper_boy.feeds.feedparser.parse") as mock_parse,
            patch("paper_boy.feeds._extract_article") as mock_extract,
            patch("paper_boy.feeds.is_safe_url", return_value=True),
        ):
            mock_parse.return_value = _make_parsed_feed(entries=entries)
            # All extractions fail
            mock_extract.return_value = None

            section = _fetch_single_feed(feed_cfg, config)

            assert len(section.articles) == 0
            # Should have stopped after _MAX_CONSECUTIVE_FAILURES, not tried all 10
            assert mock_extract.call_count == _MAX_CONSECUTIVE_FAILURES

    def test_resets_on_success(self, make_config):
        """Counter resets when an extraction succeeds — all entries attempted."""
        entries = [
            _make_feed_entry(title=f"Article {i}", link=f"https://example.com/{i}")
            for i in range(8)
        ]
        feed_cfg = MagicMock()
        feed_cfg.name = "TestFeed"
        feed_cfg.url = "https://example.com/feed"
        feed_cfg.category = ""
        config = make_config()

        # Pattern: fail, fail, success, fail, fail, success, fail, fail
        # Never hits 3 consecutive failures
        side_effects = [
            None, None,
            Article(title="OK", url="https://example.com/ok", html_content=_LONG_CONTENT),
            None, None,
            Article(title="OK2", url="https://example.com/ok2", html_content=_LONG_CONTENT),
            None, None,
        ]

        with (
            patch("paper_boy.feeds.feedparser.parse") as mock_parse,
            patch("paper_boy.feeds._extract_article") as mock_extract,
            patch("paper_boy.feeds.is_safe_url", return_value=True),
        ):
            mock_parse.return_value = _make_parsed_feed(entries=entries)
            mock_extract.side_effect = side_effects

            section = _fetch_single_feed(feed_cfg, config)

            assert len(section.articles) == 2
            # All 8 entries should be attempted (never hit 3 consecutive)
            assert mock_extract.call_count == 8


# --- Domain failure tracking ---


class TestDomainFailureTracking:
    """Test domain-level extraction failure tracking."""

    def setup_method(self):
        _reset_domain_failures()

    def test_record_and_check(self):
        """Domain is blocked after threshold failures."""
        url = "https://www.politico.com/news/article-1"
        assert not _domain_is_blocked(url)
        _record_domain_failure(url)
        assert not _domain_is_blocked(url)  # 1 failure, threshold is 2
        _record_domain_failure(url)
        assert _domain_is_blocked(url)  # 2 failures, blocked

    def test_different_domains_independent(self):
        """Failures on one domain don't affect another."""
        url_a = "https://www.politico.com/article-1"
        url_b = "https://www.axios.com/article-1"
        _record_domain_failure(url_a)
        _record_domain_failure(url_a)
        assert _domain_is_blocked(url_a)
        assert not _domain_is_blocked(url_b)

    def test_same_domain_different_paths(self):
        """Different articles on same domain share the counter."""
        _record_domain_failure("https://www.politico.com/article-1")
        _record_domain_failure("https://www.politico.com/article-2")
        assert _domain_is_blocked("https://www.politico.com/article-3")

    def test_reset_clears_all(self):
        """_reset_domain_failures clears the tracking dict."""
        _record_domain_failure("https://www.politico.com/a")
        _record_domain_failure("https://www.politico.com/b")
        assert _domain_is_blocked("https://www.politico.com/c")
        _reset_domain_failures()
        assert not _domain_is_blocked("https://www.politico.com/c")

    def test_blocked_domain_skips_fallbacks(self):
        """When domain is blocked, strategies 2-4 are skipped but 1.5 still runs.

        Domain failure is now recorded after both strategy 1 AND 1.5 fail,
        so strategy 1.5 (browser UA) always gets a chance.  When the domain
        is blocked, strategies 2 (bot UA), 3 (JSON-LD), and 4 (archive) are
        skipped to save time.
        """
        url = "https://www.politico.com/news/test-article"
        # Pre-block the domain
        _record_domain_failure("https://www.politico.com/a")
        _record_domain_failure("https://www.politico.com/b")

        with (
            patch("paper_boy.feeds._trafilatura_extract", return_value=None),
            patch("paper_boy.feeds._fetch_page", return_value=None) as mock_fetch_page,
            patch("paper_boy.feeds._extract_via_archive") as mock_archive,
        ):
            result = _extract_article_content(url, include_images=False)

            assert result is None
            # _fetch_page called once for strategy 1.5 (browser UA),
            # but NOT for strategy 2 (bot UA) — that's skipped by domain block
            assert mock_fetch_page.call_count == 1
            # archive.today should NOT be called (strategy 4 skipped)
            mock_archive.assert_not_called()

    def test_paywall_teaser_does_not_record_domain_failure(self):
        """Paywall teasers (enough words but paywall detected) should NOT
        trigger domain failure tracking.

        FT pattern: S1 returns ~170 words of paywall text. This is NOT an
        extraction failure — the site is accessible, it just needs a different
        UA (bot/outbrain). Recording this as a domain failure would block S2,
        which is exactly the strategy that works.
        """
        paywall_html = (
            "<p>Subscribe to unlock this article</p>"
            "<p>" + " ".join(["word"] * 160) + "</p>"
        )
        full_article = "<p>" + " ".join(["content"] * 500) + "</p>"

        for i in range(3):
            url = f"https://www.ft.com/content/article-{i}"
            with (
                patch("paper_boy.feeds._trafilatura_extract", return_value=paywall_html),
                patch("paper_boy.feeds._fetch_page", side_effect=[
                    "<html>paywall</html>",  # browser UA
                    "<html>full</html>",      # bot UA
                ]),
                patch("paper_boy.feeds._trafilatura_extract_from_html",
                      side_effect=[paywall_html, full_article]),
                patch("paper_boy.feeds._extract_from_json_ld", return_value=None),
                patch("paper_boy.feeds._extract_via_archive", return_value=None),
            ):
                result = _extract_article_content(url, include_images=False)
                assert result is not None
                assert "content" in result

        # After 3 paywall-teaser articles, domain should NOT be blocked
        assert not _domain_is_blocked("https://www.ft.com/content/article-4")
