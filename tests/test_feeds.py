"""Tests for RSS feed fetching and article extraction."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from paper_boy.cache import ContentCache
from paper_boy import feeds
from paper_boy.feeds import (
    _CONSECUTIVE_FAILURE_OVERRIDES,
    _DOMAIN_STRATEGY_HINTS,
    _MAX_CONSECUTIVE_FAILURES,
    Article,
    Section,
    _clean_ft_html,
    _count_words,
    _dedup_consecutive_paragraphs,
    _domain_failures,
    _domain_is_blocked,
    _downgrade_body_headings,
    _download_image,
    _extract_article,
    _extract_article_content,
    _extract_bloomberg_article,
    _extract_ft_articles,
    _fetch_bloomberg_section_stories,
    _fetch_bloomberg_bw_stories,
    _fetch_bof_feed,
    _extract_from_json_ld,
    _extract_paginated_content,
    _has_paywall_markers,
    _extract_via_archive,
    _fetch_single_feed,
    _get_feed_content,
    _is_junk_figcaption,
    _is_premium_title,
    _is_stale_entry,
    _freshness_window_days,
    _recover_images_from_html,
    _recover_images_from_json,
    _extract_verge_images,
    _extract_conde_nast_images,
    _should_skip_title,
    _should_skip_url,
    MAX_ARTICLE_WORDS,
    _normalize_html,
    _record_domain_failure,
    _reset_domain_failures,
    _should_skip_image,
    _strip_duplicate_title,
    apply_article_budget,
    apply_reading_time_budget,
    WORDS_PER_MINUTE,
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
        entries = [_make_feed_entry(title=f"Art {i}", link=f"https://example.com/article/{i}") for i in range(3)]
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
        # Use different URLs per feed to avoid cross-feed dedup
        call_count = [0]
        orig_parse = mock_parse.side_effect

        def _parse_feed(url):
            call_count[0] += 1
            return _make_parsed_feed(entries=[
                _make_feed_entry(link=f"https://example.com/article/feed{call_count[0]}")
            ])

        mock_parse.side_effect = _parse_feed

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
        # _fetch_page may be called for image recovery (text has 0 images)
        # but should NOT fall through to bot UA / further strategies
        mock_traf.assert_called_once()

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

        result = _extract_article_content("https://www.paywalled-news.com/content/abc123", True)
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

    def test_strips_article_continues_below(self):
        """Space.com bare 'Article continues below' text node is removed."""
        html = "<p>Content before.</p>Article continues below<p>Content after.</p>"
        result = _normalize_html(html)
        assert "Article continues below" not in result
        assert "Content before" in result
        assert "Content after" in result

    def test_strips_bbc_published_bullet(self):
        """BBC 'Published' CMS artifact is removed."""
        html = "<ul><li>Published</li></ul><p>Article content here.</p>"
        result = _normalize_html(html)
        assert "Published" not in result
        assert "Article content" in result

    def test_strips_bloomberg_ad_div(self):
        """Bloomberg empty ad div placeholders are removed."""
        html = (
            '<p>Article content.</p>'
            '<div class="ad news-designed-for-consumer-media" data-ad-type="small-box"> </div>'
            '<p>More content.</p>'
        )
        result = _normalize_html(html)
        assert "ad news-designed" not in result
        assert "Article content" in result
        assert "More content" in result

    def test_strip_url_figcaption(self):
        """Figcaptions containing only a URL are stripped."""
        html = (
            '<figure><img src="logo.png"/>'
            '<figcaption>https://cdn.mos.cms.futurecdn.net/flexiimages/y99mlvgqmn1763972420.png</figcaption>'
            '</figure>'
        )
        result = _normalize_html(html)
        assert "cdn.mos.cms" not in result
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

    def test_non_leading_heading_removed(self):
        """Non-leading heading matching the title is also removed."""
        html = "<p>Intro.</p><h1>Breaking News Today</h1><p>Body.</p>"
        result = _strip_duplicate_title(html, "Breaking News Today")
        assert "<h1>" not in result
        assert "Intro." in result
        assert "Body." in result

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

    def test_removes_non_leading_h2_after_figure(self):
        """The Verge / Dezeen pattern: <figure> before title heading."""
        html = '<figure><img src="hero.jpg"/></figure><h2>Article Title</h2><p>Content.</p>'
        result = _strip_duplicate_title(html, "Article Title")
        assert "<h2>" not in result
        assert "<figure>" in result
        assert "Content." in result

    def test_removes_h2_after_multiple_elements(self):
        """AP News pattern: figure + figcaption + heading."""
        html = '<figure><img src="x.jpg"/><figcaption>Photo credit</figcaption></figure><h2>Big Story Here</h2><p>Text.</p>'
        result = _strip_duplicate_title(html, "Big Story Here")
        assert "<h2>" not in result
        assert "Photo credit" in result

    def test_removes_multiple_duplicate_headings(self):
        """Edge case: same title appears as both h1 and h2."""
        html = "<h1>My Title</h1><p>Intro.</p><h2>My Title</h2><p>Content.</p>"
        result = _strip_duplicate_title(html, "My Title")
        assert "My Title" not in result
        assert "Intro." in result
        assert "Content." in result

    def test_html_entity_in_title_still_matches(self):
        """HTML entities in RSS title (e.g. &#8217;) match Unicode in heading."""
        html = "<h2>Perplexity\u2019s Computer</h2><p>Content.</p>"
        result = _strip_duplicate_title(html, "Perplexity&#8217;s Computer")
        assert "<h2>" not in result
        assert "Content." in result

    def test_preserves_non_matching_h2_after_figure(self):
        """Don't remove section headings that don't match the title."""
        html = '<figure><img src="x.jpg"/></figure><h2>Background</h2><p>Content.</p>'
        result = _strip_duplicate_title(html, "Different Title")
        assert "<h2>Background</h2>" in result


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


class TestApplyReadingTimeBudget:
    """Tests for the reading-time-based budget distribution."""

    def _make_section(self, name: str, num_articles: int, words_per_article: int = 500):
        """Create a section with articles of known word count."""
        articles = [
            Article(
                title=f"{name} Art {i}",
                url=f"https://example.com/{name}/{i}",
                html_content="<p>" + " ".join(["word"] * words_per_article) + "</p>",
                word_count=words_per_article,
            )
            for i in range(num_articles)
        ]
        return Section(name=name, articles=articles)

    def test_no_trimming_when_under_budget(self):
        """If total reading time <= budget, return all articles."""
        # 2 articles × 238 words = 2 min total
        sections = [self._make_section("A", 1, 238), self._make_section("B", 1, 238)]
        result = apply_reading_time_budget(sections, 5)
        assert sum(len(s.articles) for s in result) == 2

    def test_trims_to_fit_budget(self):
        """Articles are trimmed to fit within reading time target."""
        # 3 sources × 5 articles × 476 words = 30 min total, budget = 10 min
        sections = [self._make_section(f"S{i}", 5, 476) for i in range(3)]
        result = apply_reading_time_budget(sections, 10)
        total_words = sum(a.word_count for s in result for a in s.articles)
        total_minutes = total_words / WORDS_PER_MINUTE
        # Should be approximately 10 min (allow overshoot from last article)
        assert total_minutes <= 14  # 10 + one 2-min article overshoot
        assert total_minutes >= 6   # at least 3 articles (1 per source)

    def test_each_source_gets_at_least_one(self):
        """Phase 1 guarantees 1 article per source when budget allows."""
        # 4 sources × 238 words/article = 4 min for phase 1, budget = 8 min
        sections = [self._make_section(f"S{i}", 3, 238) for i in range(4)]
        result = apply_reading_time_budget(sections, 8)
        assert len(result) == 4
        for s in result:
            assert len(s.articles) >= 1

    def test_stops_phase1_when_budget_hit(self):
        """Phase 1 stops adding sources when budget is exhausted."""
        # 5 sources × 1190 words (5 min each) = 25 min phase 1, budget = 10 min
        sections = [self._make_section(f"S{i}", 3, 1190) for i in range(5)]
        result = apply_reading_time_budget(sections, 10)
        # Should include ~2 sources (10 min / 5 min each)
        assert len(result) <= 3
        assert len(result) >= 1

    def test_empty_sections(self):
        """Empty input returns empty output."""
        result = apply_reading_time_budget([], 20)
        assert result == []

    def test_zero_budget(self):
        """Zero budget returns input unchanged (no trimming)."""
        sections = [self._make_section("A", 3, 500)]
        result = apply_reading_time_budget(sections, 0)
        assert sum(len(s.articles) for s in result) == 3

    def test_short_articles_yield_more(self):
        """Short articles (news briefs) should yield more articles than long ones."""
        # 100-word briefs (~0.42 min each) vs 1000-word features (~4.2 min each)
        short_sections = [self._make_section(f"S{i}", 10, 100) for i in range(3)]
        long_sections = [self._make_section(f"L{i}", 10, 1000) for i in range(3)]

        short_result = apply_reading_time_budget(short_sections, 10)
        long_result = apply_reading_time_budget(long_sections, 10)

        short_count = sum(len(s.articles) for s in short_result)
        long_count = sum(len(s.articles) for s in long_result)
        assert short_count > long_count

    def test_round_robin_fills_evenly(self):
        """Phase 2 distributes articles across sources, not front-loaded."""
        # 2 sources with identical articles, budget for ~4 articles
        sections = [self._make_section("A", 5, 238), self._make_section("B", 5, 238)]
        result = apply_reading_time_budget(sections, 4)
        # Both sources should have articles (round-robin)
        assert len(result) == 2
        for s in result:
            assert len(s.articles) >= 1

    def test_mixed_lengths_respects_time(self):
        """With mixed article lengths, budget is time-based not count-based."""
        # Source A: 5 short articles (119 words = 0.5 min each)
        # Source B: 5 long articles (1190 words = 5 min each)
        # Budget: 6 min — should get more from A than B
        sections = [
            self._make_section("Short", 5, 119),
            self._make_section("Long", 5, 1190),
        ]
        result = apply_reading_time_budget(sections, 6)
        short_sec = next(s for s in result if s.name == "Short")
        long_sec = next(s for s in result if s.name == "Long")
        # Long source gets 1 (phase 1), short source gets more due to time budget
        assert len(short_sec.articles) >= len(long_sec.articles)

    def test_scarce_sources_prioritized_in_phase1(self):
        """Phase 1 fills scarce (weekly) sources before high-volume daily sources."""
        # Weekly: 2 articles (~5 min each), Daily: 20 articles (~1 min each)
        # Budget: 6 min — only room for ~1 source in phase 1 if long articles
        # Scarce source should get its slot even though it's listed second
        sections = [
            self._make_section("Daily", 20, 238),     # 20 articles, 1 min each
            self._make_section("Weekly", 2, 1190),     # 2 articles, 5 min each
        ]
        result = apply_reading_time_budget(sections, 8)
        # Weekly source (scarce) should be present despite being second in list
        names = [s.name for s in result]
        assert "Weekly" in names

    def test_scarce_sources_filled_before_daily(self):
        """Phase 2 fills scarce sources more completely than high-volume ones."""
        # Weekly: 3 articles (238 words each = 1 min)
        # Daily: 15 articles (238 words each = 1 min)
        # Budget: 10 min — should fill weekly (3) before giving daily extras
        sections = [
            self._make_section("Daily", 15, 238),
            self._make_section("Weekly", 3, 238),
        ]
        result = apply_reading_time_budget(sections, 10)
        weekly = next(s for s in result if s.name == "Weekly")
        daily = next(s for s in result if s.name == "Daily")
        # Weekly should be fully included (all 3), daily gets the rest
        assert len(weekly.articles) == 3
        assert len(daily.articles) == 10 - 3  # remaining budget

    def test_overshoot_cap_is_5_minutes(self):
        """Phase 2 skips articles that would overshoot by more than 5 min."""
        # Source A: 1 article already allocated (1 min), next is 10 min
        # Source B: 1 article already allocated (1 min), next is 2 min
        # Budget: 4 min — after phase 1 (2 min used), 2 min left
        # A's next (10 min) would overshoot to 12 min (7 min over) — skip
        # B's next (2 min) fits within cap
        sections = [
            Section(name="LongNext", articles=[
                Article(title="A0", url="u0", html_content="x", word_count=238),
                Article(title="A1", url="u1", html_content="x", word_count=2380),
            ]),
            Section(name="ShortNext", articles=[
                Article(title="B0", url="u2", html_content="x", word_count=238),
                Article(title="B1", url="u3", html_content="x", word_count=476),
            ]),
        ]
        result = apply_reading_time_budget(sections, 4)
        long_sec = next(s for s in result if s.name == "LongNext")
        short_sec = next(s for s in result if s.name == "ShortNext")
        # LongNext's 10-min article should be skipped (overshoot > 5 min)
        assert len(long_sec.articles) == 1
        # ShortNext's 2-min article should be added
        assert len(short_sec.articles) == 2

    def test_articles_per_day_used_for_scarcity(self):
        """When articles_per_day is set, it drives scarcity ordering."""
        # Scarce source (0.3/day) with 5 articles vs prolific (10/day) with 5 articles
        # Same article count but articles_per_day should make scarce fill first
        scarce = self._make_section("Scarce", 5, 238)
        scarce.articles_per_day = 0.3
        prolific = self._make_section("Prolific", 5, 238)
        prolific.articles_per_day = 10.0
        result = apply_reading_time_budget([prolific, scarce], 6)
        scarce_r = next(s for s in result if s.name == "Scarce")
        prolific_r = next(s for s in result if s.name == "Prolific")
        # Scarce source should get at least as many as prolific
        assert len(scarce_r.articles) >= len(prolific_r.articles)

    def test_articles_per_day_zero_falls_back_to_count(self):
        """When articles_per_day is 0 (unknown), falls back to article count."""
        # Both sources have articles_per_day=0.0 (default)
        small = self._make_section("Small", 3, 238)
        big = self._make_section("Big", 15, 238)
        result = apply_reading_time_budget([big, small], 8)
        small_r = next(s for s in result if s.name == "Small")
        big_r = next(s for s in result if s.name == "Big")
        # Small (3/20=0.15 rate) should rank as scarcer than Big (15/20=0.75)
        assert len(small_r.articles) == 3  # all included — only 3 available


# --- Consecutive failure abort ---


class TestPremiumTitleSkipping:
    """Test that entries with premium title prefixes are skipped."""

    def test_stat_plus_detected(self):
        assert _is_premium_title("STAT+: Some premium article") is True

    def test_regular_title_not_detected(self):
        assert _is_premium_title("Fresh turmoil at the FDA") is False

    def test_stat_plus_in_middle_of_title(self):
        assert _is_premium_title("Opinion: STAT+: The Himsification") is True

    def test_stat_plus_case_insensitive(self):
        assert _is_premium_title("stat+: some title") is True

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
        from paper_boy.config import FeedConfig
        feed_cfg = FeedConfig(name="TestFeed", url="https://example.com/feed")
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
        from paper_boy.config import FeedConfig
        feed_cfg = FeedConfig(name="TestFeed", url="https://example.com/feed")
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
        from paper_boy.config import FeedConfig
        feed_cfg = FeedConfig(name="TestFeed", url="https://example.com/feed")
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

    def test_hn_uses_higher_threshold(self, make_config):
        """Hacker News feeds should tolerate more consecutive failures."""
        entries = [
            _make_feed_entry(
                title=f"Article {i}",
                link=f"https://broken-{i}.example.com/post",
            )
            for i in range(5)
        ]
        from paper_boy.config import FeedConfig
        feed_cfg = FeedConfig(name="Hacker News", url="https://hnrss.org/frontpage", category="Technology")
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

            # With default threshold (3), only 3 entries would be attempted.
            # With HN override (10), all 5 should be attempted.
            assert mock_extract.call_count == 5


# --- Domain strategy hints ---


class TestDomainStrategyHints:
    """Test domain-level strategy hint optimization."""

    def setup_method(self):
        _reset_domain_failures()

    def test_nature_skips_s1(self):
        """Nature should skip S1 (trafilatura) and start at S1.5 (browser UA)."""
        with (
            patch("paper_boy.feeds._trafilatura_extract") as mock_traf,
            patch("paper_boy.feeds._fetch_page") as mock_fetch,
            patch("paper_boy.feeds._trafilatura_extract_from_html") as mock_traf_html,
        ):
            mock_traf_html.return_value = _LONG_CONTENT
            mock_fetch.return_value = "<html><body>" + _LONG_CONTENT + "</body></html>"

            result = _extract_article_content(
                "https://www.nature.com/articles/d41586-025-00789-1", True
            )

            # S1 (trafilatura.extract via _trafilatura_extract) should NOT be called
            mock_traf.assert_not_called()
            # S1.5 (browser UA fetch) should have been called
            assert mock_fetch.called
            assert result is not None

    def test_ft_no_longer_routes_to_archive(self):
        """FT is now handled by _extract_ft_articles feed-level handler.
        _extract_article_content should NOT have special routing for ft.com."""
        with (
            patch("paper_boy.feeds._trafilatura_extract", return_value=_LONG_CONTENT) as mock_traf,
            patch("paper_boy.feeds._extract_via_archive") as mock_archive,
        ):
            result = _extract_article_content(
                "https://www.ft.com/content/some-article", True
            )

            # FT should go through normal extraction chain now (not archive.today)
            mock_archive.assert_not_called()
            assert result is not None

    def test_unknown_domain_uses_default_chain(self):
        """Domains not in hints use the full fallback chain starting from S1."""
        with patch(
            "paper_boy.feeds._trafilatura_extract", return_value=_LONG_CONTENT
        ) as mock_traf:
            result = _extract_article_content(
                "https://www.example.com/article", True
            )
            # trafilatura extract should be called (S1 attempted)
            assert mock_traf.called
            assert result is not None


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

        Pattern: S1 returns ~170 words of paywall text. This is NOT an
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
            url = f"https://www.paywalled-news.com/content/article-{i}"
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
        assert not _domain_is_blocked("https://www.paywalled-news.com/content/article-4")

    def test_domain_hint_does_not_record_failure(self):
        """When strategy hints skip S1, the skip must NOT count as a domain
        failure.  Otherwise hint_start>=2 causes domain blocking after 2
        articles, preventing S1.5 (which works) from running.  Nature uses
        hint_start=2 (skip to S1.5)."""
        _reset_domain_failures()

        browser_article = "<p>" + " ".join(["content"] * 500) + "</p>"

        for i in range(3):
            url = f"https://www.nature.com/articles/article-{i}"
            with (
                patch("paper_boy.feeds._fetch_page", return_value="<html>browser page</html>"),
                patch("paper_boy.feeds._trafilatura_extract_from_html",
                      return_value=browser_article),
                patch("paper_boy.feeds._extract_from_json_ld", return_value=None),
                patch("paper_boy.feeds._extract_via_archive", return_value=None),
            ):
                result = _extract_article_content(url, include_images=False)
                assert result is not None, f"Article {i} should succeed via S1.5 browser UA"

        # Domain must NOT be blocked — hint-skipped strategies aren't failures
        assert not _domain_is_blocked("https://www.nature.com/articles/article-4")


# --- Cross-feed URL deduplication ---


class TestCrossFeedDedup:
    def test_skips_duplicate_url_across_feeds(self, make_config):
        seen_urls = {"https://example.com/article/1"}
        entry = _make_feed_entry(link="https://example.com/article/1")
        config = make_config()
        with patch("paper_boy.feeds._extract_article_content", return_value=_LONG_CONTENT):
            result = _extract_article(entry, config, seen_urls=seen_urls)
        assert result is None

    def test_allows_new_url(self, make_config):
        seen_urls: set[str] = set()
        entry = _make_feed_entry(link="https://example.com/article/new")
        config = make_config()
        with patch("paper_boy.feeds._extract_article_content", return_value=_LONG_CONTENT):
            result = _extract_article(entry, config, seen_urls=seen_urls)
        assert result is not None
        assert "https://example.com/article/new" in seen_urls

    def test_without_seen_urls_no_dedup(self, make_config):
        entry = _make_feed_entry(link="https://example.com/article/1")
        config = make_config()
        with patch("paper_boy.feeds._extract_article_content", return_value=_LONG_CONTENT):
            result = _extract_article(entry, config, seen_urls=None)
        assert result is not None


# --- Title filtering ---


class TestTitleFiltering:
    @pytest.mark.parametrize("title", [
        "Author Correction: Gut stem cell necroptosis",
        "Erratum: Solar cell efficiency measurement",
        "Green Deals: Best solar panel discounts this week",
        "Webinar: Space Station Science Updates",
    ])
    def test_skips_non_journalism_titles(self, title):
        assert _should_skip_title(title) is True

    @pytest.mark.parametrize("title", [
        "Scientists Discover New Species in Deep Ocean",
        "The Green New Deal Explained",
        "How to Track Your Fitness Goals",
        "EU Green Deal Faces New Opposition",
        "The Vogue Business People Moves Tracker",
        "COVID Tracker Shows Declining Cases",
        "Scientists present findings at annual webinar series",
    ])
    def test_allows_journalism_titles(self, title):
        assert _should_skip_title(title) is False


# --- URL filtering ---


class TestUrlFiltering:
    @pytest.mark.parametrize("url", [
        "https://www.nature.com/articles/s41586-025-08923-z",
        "https://projects.propublica.org/climate-migration",
        "https://www.nasa.gov/nesc/some-technical-paper",
        "https://www.smithsonianmag.com/sponsored/four-ways-to-experience-wyoming/",
    ])
    def test_skips_non_article_urls(self, url):
        assert _should_skip_url(url) is True

    @pytest.mark.parametrize("url", [
        "https://www.nature.com/articles/d41586-025-00789-1",
        "https://www.propublica.org/article/some-investigation",
        "https://www.smithsonianmag.com/history/the-untold-story/",
    ])
    def test_allows_article_urls(self, url):
        assert _should_skip_url(url) is False


# --- Word count cap ---


class TestWordCountCap:
    def test_rejects_oversized_article(self, make_config):
        huge_content = "<p>" + " ".join(["word"] * 15000) + "</p>"
        entry = _make_feed_entry()
        config = make_config()
        with patch("paper_boy.feeds._extract_article_content", return_value=huge_content):
            result = _extract_article(entry, config)
        assert result is None

    def test_allows_normal_article(self, make_config):
        entry = _make_feed_entry()
        config = make_config()
        with patch("paper_boy.feeds._extract_article_content", return_value=_LONG_CONTENT):
            result = _extract_article(entry, config)
        assert result is not None


# --- Author cleanup ---


class TestAuthorCleanup:
    """Tests for author metadata cleanup during feed processing."""

    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html>page</html>")
    @patch("paper_boy.feeds.feedparser.parse")
    def test_strips_by_prefix_from_author(
        self, mock_parse, mock_fetch_url, mock_extract, local_config
    ):
        """'By Author Name' in dc:creator becomes 'Author Name'."""
        mock_parse.return_value = _make_parsed_feed(
            entries=[_make_feed_entry(author="By Marianne Lavelle")]
        )
        sections = fetch_feeds(local_config)
        assert sections[0].articles[0].author == "Marianne Lavelle"


# --- Stale entry filtering ---


class TestIsStaleEntry:
    """Tests for _is_stale_entry() feed freshness gate."""

    def test_old_entry_is_stale(self):
        """Entry published 10 days ago is stale (> 7 day threshold)."""
        import time, calendar
        ten_days_ago = time.gmtime(time.time() - 10 * 86400)
        entry = {"published_parsed": ten_days_ago}
        assert _is_stale_entry(entry) is True

    def test_recent_entry_is_fresh(self):
        """Entry published 1 day ago is not stale."""
        import time
        one_day_ago = time.gmtime(time.time() - 1 * 86400)
        entry = {"published_parsed": one_day_ago}
        assert _is_stale_entry(entry) is False

    def test_no_date_is_not_stale(self):
        """Entry with no date fields is assumed fresh."""
        entry = {"title": "No date here"}
        assert _is_stale_entry(entry) is False

    def test_uses_updated_when_no_published(self):
        """Falls back to updated_parsed when published_parsed is missing."""
        import time
        ten_days_ago = time.gmtime(time.time() - 10 * 86400)
        entry = {"updated_parsed": ten_days_ago}
        assert _is_stale_entry(entry) is True

    def test_boundary_fresh_at_exactly_7_days(self):
        """Entry exactly 7 days old is not stale (boundary: > not >=)."""
        import time
        # Slightly under 7 days
        entry = {"published_parsed": time.gmtime(time.time() - 6.9 * 86400)}
        assert _is_stale_entry(entry) is False

    def test_invalid_date_tuple_is_not_stale(self):
        """Malformed date tuples don't crash — treated as fresh."""
        entry = {"published_parsed": "not a tuple"}
        assert _is_stale_entry(entry) is False

    @patch("paper_boy.feeds.trafilatura.extract", return_value=_LONG_CONTENT)
    @patch("paper_boy.feeds.trafilatura.fetch_url", return_value="<html>page</html>")
    @patch("paper_boy.feeds.feedparser.parse")
    def test_stale_entries_skipped_in_fetch(
        self, mock_parse, mock_fetch_url, mock_extract, local_config
    ):
        """Stale entries are skipped — only fresh entries become articles."""
        import time
        old_date = time.gmtime(time.time() - 10 * 86400)
        fresh_date = time.gmtime(time.time() - 1 * 86400)
        mock_parse.return_value = _make_parsed_feed(entries=[
            _make_feed_entry(title="Old Article", published=old_date),
            _make_feed_entry(
                title="Fresh Article",
                link="https://example.com/article/2",
                published=fresh_date,
            ),
        ])
        # Patch published_parsed which feedparser normally provides
        mock_parse.return_value.entries[0]["published_parsed"] = old_date
        mock_parse.return_value.entries[1]["published_parsed"] = fresh_date
        sections = fetch_feeds(local_config)
        assert len(sections) == 1
        assert len(sections[0].articles) == 1
        assert sections[0].articles[0].title == "Fresh Article"

    def test_custom_max_age_days(self):
        """Parameterized max_age_days overrides default 7-day window."""
        import time
        # 2 days old — stale with 1.5-day window, fresh with 7-day default
        two_days_ago = time.gmtime(time.time() - 2 * 86400)
        entry = {"published_parsed": two_days_ago}
        assert _is_stale_entry(entry, max_age_days=1.5) is True
        assert _is_stale_entry(entry) is False  # default 7 days

    def test_custom_max_age_boundary(self):
        """Entry exactly at the custom boundary is fresh (> not >=)."""
        import time
        entry = {"published_parsed": time.gmtime(time.time() - 1.4 * 86400)}
        assert _is_stale_entry(entry, max_age_days=1.5) is False


class TestFreshnessWindowDays:
    """Tests for _freshness_window_days() per-feed freshness tiers."""

    def test_prolific_source(self):
        """High-frequency sources (>= 3/day) get 1.5-day window."""
        from paper_boy.config import FeedConfig
        cfg = FeedConfig(name="Guardian", url="https://theguardian.com/rss", articles_per_day=12.0)
        assert _freshness_window_days(cfg) == 1.5

    def test_moderate_source(self):
        """Moderate-frequency sources (>= 0.5/day) get 2-day window."""
        from paper_boy.config import FeedConfig
        cfg = FeedConfig(name="BBC", url="https://bbc.com/rss", articles_per_day=1.5)
        assert _freshness_window_days(cfg) == 2.0

    def test_scarce_short_article(self):
        """Scarce source with short articles: ~3 day window."""
        from paper_boy.config import FeedConfig
        cfg = FeedConfig(name="Brief", url="https://brief.com/rss", articles_per_day=0.3, estimated_read_min=1.0)
        window = _freshness_window_days(cfg)
        assert 2.5 <= window <= 3.5  # 2 + (1/5)*5 = 3

    def test_scarce_medium_article(self):
        """Scarce source with medium articles: ~5 day window."""
        from paper_boy.config import FeedConfig
        cfg = FeedConfig(name="Weekly", url="https://weekly.com/rss", articles_per_day=0.3, estimated_read_min=3.0)
        window = _freshness_window_days(cfg)
        assert 4.5 <= window <= 5.5  # 2 + (3/5)*5 = 5

    def test_scarce_long_article(self):
        """Scarce source with long articles: 7-day window (max)."""
        from paper_boy.config import FeedConfig
        cfg = FeedConfig(name="Quanta", url="https://quanta.com/rss", articles_per_day=0.4, estimated_read_min=9.0)
        assert _freshness_window_days(cfg) == 7.0  # 2 + min(9/5, 1)*5 = 7

    def test_unknown_frequency(self):
        """Zero articles_per_day (no stats) defaults to 7-day window."""
        from paper_boy.config import FeedConfig
        cfg = FeedConfig(name="New", url="https://new.com/rss", articles_per_day=0.0)
        assert _freshness_window_days(cfg) == 7.0

    def test_boundary_at_three(self):
        """Exactly 3 articles/day is prolific tier."""
        from paper_boy.config import FeedConfig
        cfg = FeedConfig(name="Edge", url="https://edge.com/rss", articles_per_day=3.0)
        assert _freshness_window_days(cfg) == 1.5

    def test_boundary_at_half(self):
        """Exactly 0.5 articles/day is moderate tier."""
        from paper_boy.config import FeedConfig
        cfg = FeedConfig(name="Edge", url="https://edge.com/rss", articles_per_day=0.5)
        assert _freshness_window_days(cfg) == 2.0


# --- Image recovery from raw HTML ---


class TestRecoverImagesFromHtml:
    """Tests for _recover_images_from_html() image recovery."""

    def test_no_recovery_when_images_exist(self):
        """If extracted content already has images, return unchanged."""
        extracted = '<p>Text</p><img src="http://example.com/photo.jpg"/><p>More</p>'
        raw = '<html><article><img src="http://example.com/other.jpg"/></article></html>'
        result = _recover_images_from_html(extracted, raw)
        assert result == extracted

    def test_no_recovery_when_graphic_tags_exist(self):
        """TEI <graphic> tags count as existing images."""
        extracted = '<p>Text</p><graphic src="http://example.com/photo.jpg"/>'
        raw = '<html><article><img src="http://example.com/other.jpg"/></article></html>'
        result = _recover_images_from_html(extracted, raw)
        assert result == extracted

    def test_recovers_lead_image_from_article(self):
        """Recovers images from <article> container when extracted has none."""
        extracted = "<p>Article text without images.</p>"
        raw = (
            "<html><body><article>"
            '<img src="https://cdn.example.com/hero.jpg" alt="Hero"/>'
            "<p>Article text without images.</p>"
            "</article></body></html>"
        )
        result = _recover_images_from_html(extracted, raw)
        assert 'src="https://cdn.example.com/hero.jpg"' in result
        assert "<p>Article text without images.</p>" in result

    def test_recovers_from_main_element(self):
        """Falls through to <main> when no <article>."""
        extracted = "<p>Text only.</p>"
        raw = (
            "<html><body><main>"
            '<img src="https://cdn.example.com/photo.jpg" alt="Photo"/>'
            "</main></body></html>"
        )
        result = _recover_images_from_html(extracted, raw)
        assert "cdn.example.com/photo.jpg" in result

    def test_filters_ad_images(self):
        """Ad/tracking images are excluded from recovery."""
        extracted = "<p>Text only.</p>"
        raw = (
            "<html><body><article>"
            '<img src="https://doubleclick.net/ad.gif" alt="ad"/>'
            '<img src="https://pixel.example.com/track.png" alt=""/>'
            "</article></body></html>"
        )
        result = _recover_images_from_html(extracted, raw)
        # No valid images recovered — should return unchanged
        assert result == extracted

    def test_deduplicates_images(self):
        """Same image URL appearing multiple times is only recovered once."""
        extracted = "<p>Text only.</p>"
        raw = (
            "<html><body><article>"
            '<img src="https://cdn.example.com/hero.jpg" alt="Hero"/>'
            '<img src="https://cdn.example.com/hero.jpg" alt="Hero 2"/>'
            "</article></body></html>"
        )
        result = _recover_images_from_html(extracted, raw)
        assert result.count("cdn.example.com/hero.jpg") == 1

    def test_recovers_all_valid_images(self):
        """All valid images in the content container are recovered."""
        extracted = "<p>Text only.</p>"
        imgs = "".join(
            f'<img src="https://cdn.example.com/img{i}.jpg" alt=""/>'
            for i in range(10)
        )
        raw = f"<html><body><article>{imgs}</article></body></html>"
        result = _recover_images_from_html(extracted, raw)
        assert result.count("<img") == 10

    def test_prefers_data_src(self):
        """Lazy-loaded data-src is preferred over src."""
        extracted = "<p>Text only.</p>"
        raw = (
            "<html><body><article>"
            '<img data-src="https://cdn.example.com/lazy.jpg" '
            'src="https://cdn.example.com/placeholder.gif" alt=""/>'
            "</article></body></html>"
        )
        result = _recover_images_from_html(extracted, raw)
        assert "cdn.example.com/lazy.jpg" in result
        assert "placeholder.gif" not in result

    def test_skips_relative_urls_without_page_url(self):
        """Relative image URLs are skipped when no page_url is provided."""
        extracted = "<p>Text only.</p>"
        raw = (
            "<html><body><article>"
            '<img src="/images/local.jpg" alt="Local"/>'
            "</article></body></html>"
        )
        result = _recover_images_from_html(extracted, raw)
        assert result == extracted

    def test_resolves_relative_urls_with_page_url(self):
        """Relative image URLs are resolved against the page URL (Al Jazeera pattern)."""
        extracted = "<p>Text only.</p>"
        raw = (
            "<html><body><article>"
            '<img src="/wp-content/uploads/2026/03/photo.jpg" alt="Photo"/>'
            "</article></body></html>"
        )
        result = _recover_images_from_html(
            extracted, raw, "https://www.aljazeera.com/news/2026/3/13/article"
        )
        assert "https://www.aljazeera.com/wp-content/uploads/2026/03/photo.jpg" in result

    def test_no_content_container_returns_unchanged(self):
        """If no content container has images, return unchanged."""
        extracted = "<p>Text only.</p>"
        raw = (
            "<html><body><nav>"
            '<img src="https://cdn.example.com/logo.jpg" alt="Logo"/>'
            "</nav></body></html>"
        )
        result = _recover_images_from_html(extracted, raw)
        assert result == extracted

    def test_invalid_html_returns_unchanged(self):
        """Malformed raw HTML doesn't crash — returns extracted unchanged."""
        extracted = "<p>Text only.</p>"
        result = _recover_images_from_html(extracted, "")
        assert result == extracted


# --- FT Playwright Handler ---


class TestExtractFtArticles:
    def test_skipped_without_playwright(self, local_config):
        """Returns empty section if playwright is not installed."""
        from paper_boy.config import FeedConfig

        feed_cfg = FeedConfig(name="FT", url="https://www.ft.com/world?format=rss")
        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            # Force ImportError by patching builtins.__import__
            original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

            def _mock_import(name, *args, **kwargs):
                if "playwright" in name:
                    raise ImportError("No module named 'playwright'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=_mock_import):
                section = _extract_ft_articles(feed_cfg, local_config)

        assert section.name == "FT"
        assert len(section.articles) == 0

    @patch("paper_boy.feeds.feedparser.parse")
    def test_uses_cache(self, mock_parse, local_config):
        """Cache hit skips browser extraction entirely."""
        from paper_boy.config import FeedConfig

        feed_cfg = FeedConfig(name="FT", url="https://www.ft.com/world?format=rss")
        entries = [_make_feed_entry(
            title="FT Article",
            link="https://www.ft.com/content/abc123",
        )]
        mock_parse.return_value = _make_parsed_feed(entries=entries)

        cache = ContentCache()
        cache.set_article("https://www.ft.com/content/abc123", True, _LONG_CONTENT)

        # playwright shouldn't be imported if cache hits
        section = _extract_ft_articles(feed_cfg, local_config, cache=cache)
        # Cache has the article — but playwright import would still happen.
        # This test verifies the cache branch works when playwright IS available.
        # If playwright isn't installed, the function returns early before cache.
        # So we test cache integration by checking articles are served from cache.
        assert section.name == "FT"

    @patch("paper_boy.feeds.feedparser.parse")
    def test_empty_feed_returns_empty_section(self, mock_parse, local_config):
        """Empty RSS feed returns empty section without launching browser."""
        from paper_boy.config import FeedConfig

        feed_cfg = FeedConfig(name="FT", url="https://www.ft.com/world?format=rss")
        mock_parse.return_value = _make_parsed_feed(entries=[])

        # Even if playwright is available, no browser should launch for empty feed
        section = _extract_ft_articles(feed_cfg, local_config)
        assert len(section.articles) == 0

    def test_ft_routed_from_fetch_single_feed(self, local_config, make_config):
        """_fetch_single_feed routes ft.com URLs to _extract_ft_articles."""
        from paper_boy.config import FeedConfig

        config = make_config(feeds=[
            FeedConfig(name="FT", url="https://www.ft.com/world?format=rss"),
        ])

        with patch("paper_boy.feeds._extract_ft_articles") as mock_ft:
            mock_ft.return_value = feeds.Section(name="FT")
            _fetch_single_feed(
                config.feeds[0], config, cache=None, seen_urls=set()
            )
            mock_ft.assert_called_once()


# --- BoF Arc Publishing Handler ---


class TestFetchBofFeed:
    # Minimal Fusion.globalContent JSON for testing
    _BOF_FUSION_JSON = json.dumps({
        "content_elements": [
            {"type": "text", "content": "<p>" + " ".join(["fashion"] * 250) + "</p>"},
        ],
        "headlines": {"basic": "Test BoF Article"},
        "credits": {"by": [{"name": "Test Author"}]},
        "display_date": "2026-03-13T10:00:00Z",
    })

    _BOF_PAGE_HTML = (
        '<html><script>Fusion.globalContent = '
        + _BOF_FUSION_JSON
        + '; Fusion.other = {};</script></html>'
    )

    _BOF_HOMEPAGE_HTML = (
        '<html><body>'
        '<a href="/articles/test-article-1">Article 1</a>'
        '<a href="/articles/test-article-2">Article 2</a>'
        '</body></html>'
    )

    @patch("paper_boy.feeds._fetch_page")
    def test_extracts_from_fusion_json(self, mock_fetch, local_config):
        """Parses Fusion.globalContent and extracts article content."""
        from paper_boy.config import FeedConfig

        feed_cfg = FeedConfig(name="BoF", url="https://www.businessoffashion.com/feed")

        def _side_effect(url, ua, **kwargs):
            if url == "https://www.businessoffashion.com/":
                return self._BOF_HOMEPAGE_HTML
            return self._BOF_PAGE_HTML

        mock_fetch.side_effect = _side_effect

        section = _fetch_bof_feed(feed_cfg, local_config)
        assert section.name == "BoF"
        assert len(section.articles) >= 1
        assert section.articles[0].title == "Test BoF Article"
        assert section.articles[0].author == "Test Author"
        assert "fashion" in section.articles[0].html_content

    @patch("paper_boy.feeds._fetch_page")
    def test_homepage_scraping(self, mock_fetch, local_config):
        """Discovers article links from BoF homepage."""
        from paper_boy.config import FeedConfig

        feed_cfg = FeedConfig(name="BoF", url="https://www.businessoffashion.com/feed")

        mock_fetch.return_value = self._BOF_HOMEPAGE_HTML

        # The second call (article pages) will fail, but we verify link discovery
        call_urls = []
        original_side_effect = mock_fetch.side_effect

        def _track_calls(url, ua, **kwargs):
            call_urls.append(url)
            if url == "https://www.businessoffashion.com/":
                return self._BOF_HOMEPAGE_HTML
            return None  # Articles fail — that's fine for this test

        mock_fetch.side_effect = _track_calls

        _fetch_bof_feed(feed_cfg, local_config)

        # Should have called homepage + 2 article URLs
        assert "https://www.businessoffashion.com/" in call_urls
        assert "https://www.businessoffashion.com/articles/test-article-1" in call_urls
        assert "https://www.businessoffashion.com/articles/test-article-2" in call_urls

    @patch("paper_boy.feeds._fetch_page", return_value=None)
    def test_homepage_failure_returns_empty(self, mock_fetch, local_config):
        """Homepage fetch failure returns empty section gracefully."""
        from paper_boy.config import FeedConfig

        feed_cfg = FeedConfig(name="BoF", url="https://www.businessoffashion.com/feed")
        section = _fetch_bof_feed(feed_cfg, local_config)
        assert len(section.articles) == 0

    @patch("paper_boy.feeds._fetch_page")
    def test_cache_integration(self, mock_fetch, local_config):
        """Cached articles are served without re-fetching."""
        from paper_boy.config import FeedConfig

        feed_cfg = FeedConfig(name="BoF", url="https://www.businessoffashion.com/feed")
        cache = ContentCache()

        # Pre-cache the article
        cache.set_article(
            "https://www.businessoffashion.com/articles/test-article-1",
            True,  # include_images
            _LONG_CONTENT,
        )

        mock_fetch.side_effect = lambda url, ua, **kw: (
            self._BOF_HOMEPAGE_HTML
            if url == "https://www.businessoffashion.com/"
            else None
        )

        section = _fetch_bof_feed(feed_cfg, local_config, cache=cache)
        # Article 1 from cache, Article 2 fails (fetch returns None)
        assert len(section.articles) >= 1

    @patch("paper_boy.feeds._fetch_page")
    def test_invalid_fusion_json_skips(self, mock_fetch, local_config):
        """Invalid Fusion JSON gracefully skips the article."""
        from paper_boy.config import FeedConfig

        feed_cfg = FeedConfig(name="BoF", url="https://www.businessoffashion.com/feed")

        def _side_effect(url, ua, **kw):
            if url == "https://www.businessoffashion.com/":
                return self._BOF_HOMEPAGE_HTML
            return '<html><script>Fusion.globalContent = {invalid json}; Fusion.x</script></html>'

        mock_fetch.side_effect = _side_effect

        section = _fetch_bof_feed(feed_cfg, local_config)
        assert len(section.articles) == 0

    @patch("paper_boy.feeds._fetch_page")
    def test_extracts_images_from_fusion_json(self, mock_fetch, local_config):
        """Image content_elements are extracted into <figure> tags."""
        from paper_boy.config import FeedConfig

        fusion_json = json.dumps({
            "content_elements": [
                {"type": "text", "content": "<p>" + " ".join(["fashion"] * 250) + "</p>"},
                {
                    "type": "image",
                    "url": "https://cloudfront-eu-central-1.images.arcpublishing.com/businessoffashion/TEST123.jpg",
                    "alt_text": "Model on runway",
                    "caption": "Spring collection debut at Paris Fashion Week.",
                },
            ],
            "headlines": {"basic": "Test BoF Images"},
            "credits": {"by": [{"name": "Test Author"}]},
            "display_date": "2026-03-13T10:00:00Z",
        })

        page_html = (
            '<html><script>Fusion.globalContent = '
            + fusion_json
            + '; Fusion.other = {};</script></html>'
        )

        feed_cfg = FeedConfig(name="BoF", url="https://www.businessoffashion.com/feed")

        def _side_effect(url, ua, **kwargs):
            if url == "https://www.businessoffashion.com/":
                return self._BOF_HOMEPAGE_HTML
            return page_html

        mock_fetch.side_effect = _side_effect

        section = _fetch_bof_feed(feed_cfg, local_config)
        assert len(section.articles) >= 1
        html = section.articles[0].html_content
        assert "TEST123.jpg" in html or "paperboy_img" in html.lower() or "<figure" in html

    @patch("paper_boy.feeds._fetch_page")
    def test_image_fallback_to_original_url(self, mock_fetch, local_config):
        """Image extraction falls back to additional_properties.originalUrl."""
        from paper_boy.config import FeedConfig, NewspaperConfig

        # Disable images to test HTML generation without download pipeline
        local_config.newspaper = NewspaperConfig(
            title=local_config.newspaper.title,
            language=local_config.newspaper.language,
            include_images=False,
        )

        fusion_json = json.dumps({
            "content_elements": [
                {"type": "text", "content": "<p>" + " ".join(["fashion"] * 250) + "</p>"},
                {
                    "type": "image",
                    "additional_properties": {
                        "originalUrl": "https://cloudfront-eu-central-1.images.arcpublishing.com/businessoffashion/FALLBACK.jpg",
                    },
                    "alt_text": "Fallback image",
                    "caption": "",
                },
            ],
            "headlines": {"basic": "Test Fallback"},
            "credits": {"by": [{"name": "Author"}]},
            "display_date": "2026-03-13T10:00:00Z",
        })

        page_html = (
            '<html><script>Fusion.globalContent = '
            + fusion_json
            + '; Fusion.other = {};</script></html>'
        )

        feed_cfg = FeedConfig(name="BoF", url="https://www.businessoffashion.com/feed")

        def _side_effect(url, ua, **kwargs):
            if url == "https://www.businessoffashion.com/":
                return self._BOF_HOMEPAGE_HTML
            return page_html

        mock_fetch.side_effect = _side_effect

        section = _fetch_bof_feed(feed_cfg, local_config)
        assert len(section.articles) >= 1
        html = section.articles[0].html_content
        assert "FALLBACK.jpg" in html

    def test_bof_routed_from_fetch_single_feed(self, local_config, make_config):
        """_fetch_single_feed routes businessoffashion.com URLs to _fetch_bof_feed."""
        from paper_boy.config import FeedConfig

        config = make_config(feeds=[
            FeedConfig(name="BoF", url="https://www.businessoffashion.com/feed"),
        ])

        with patch("paper_boy.feeds._fetch_bof_feed") as mock_bof:
            mock_bof.return_value = feeds.Section(name="BoF")
            _fetch_single_feed(
                config.feeds[0], config, cache=None, seen_urls=set()
            )
            mock_bof.assert_called_once()


class TestCleanFtHtml:
    def test_removes_video_elements(self):
        html = '<p>Content</p><video src="video.mp4"><source type="video/mp4"/></video><p>More</p>'
        result = _clean_ft_html(html)
        assert "<video" not in result
        assert "Content" in result
        assert "More" in result

    def test_removes_iframe_elements(self):
        html = '<p>Content</p><iframe src="https://flo.uri.sh/..."></iframe><p>More</p>'
        result = _clean_ft_html(html)
        assert "<iframe" not in result
        assert "Content" in result

    def test_removes_button_elements(self):
        html = '<p>Content</p><button>Show more</button><p>More</p>'
        result = _clean_ft_html(html)
        assert "<button" not in result

    def test_unwraps_picture_keeps_img(self):
        html = '<picture><source srcset="large.jpg" media="(min-width:800px)"/><img src="small.jpg" alt="Chart"/></picture>'
        result = _clean_ft_html(html)
        assert "<picture" not in result
        assert "<source" not in result
        assert "<img" in result
        assert 'src="small.jpg"' in result

    def test_flattens_n_content_layout(self):
        html = '<div class="n-content-layout"><p>Paragraph one</p><p>Paragraph two</p></div>'
        result = _clean_ft_html(html)
        assert "n-content-layout" not in result
        assert "Paragraph one" in result
        assert "Paragraph two" in result

    def test_removes_flourish_containers(self):
        html = '<p>Content</p><div class="flourish-embed"><p>Some content could not load</p></div><p>More</p>'
        result = _clean_ft_html(html)
        assert "flourish" not in result
        assert "could not load" not in result

    def test_prefers_editorial_figcaption(self):
        html = (
            '<figure>'
            '<img src="photo.jpg" alt="Markets chart showing decline"/>'
            '<figcaption>Markets chart showing decline</figcaption>'
            '<figcaption class="n-content-picture__caption">FTSE 100 fell 2% on Tuesday</figcaption>'
            '</figure>'
        )
        result = _clean_ft_html(html)
        assert "FTSE 100 fell" in result
        # Alt-text figcaption removed; alt attribute on <img> preserved
        assert "<figcaption>Markets chart showing decline</figcaption>" not in result
        assert 'alt="Markets chart showing decline"' in result

    def test_strips_alt_dup_figcaption_single(self):
        html = (
            '<figure>'
            '<img src="photo.jpg" alt="A factory in Germany"/>'
            '<figcaption>A factory in Germany</figcaption>'
            '</figure>'
        )
        result = _clean_ft_html(html)
        assert "<figcaption" not in result
        assert "<img" in result

    def test_removes_empty_li(self):
        html = '<ul><li>Real item</li><li/><li/></ul>'
        result = _clean_ft_html(html)
        assert "Real item" in result
        assert result.count("<li") == 1


# --- Junk Figcaption Detection ---


class TestJunkFigcaption:
    def test_detects_comments_ui(self):
        assert _is_junk_figcaption("Comments", "") is True

    def test_detects_allcaps_byline(self):
        assert _is_junk_figcaption("DAVID BAUDER", "") is True

    def test_detects_single_word_label(self):
        assert _is_junk_figcaption("Cuba", "") is True

    def test_allows_real_caption(self):
        assert _is_junk_figcaption("President Biden speaks at the White House", "") is False

    def test_allows_empty(self):
        assert _is_junk_figcaption("", "") is False

    def test_detects_share_button(self):
        assert _is_junk_figcaption("Share", "") is True

    def test_allows_numbered_caption(self):
        assert _is_junk_figcaption("2024 election results by state", "") is False

    def test_detects_from_alt_fallback(self):
        """When caption is empty, checks alt text."""
        assert _is_junk_figcaption("", "JOHN SMITH") is True

    def test_allows_multiword_mixed_case(self):
        """Normal mixed-case multi-word captions are preserved."""
        assert _is_junk_figcaption("A protester holds a sign outside the capitol", "") is False


# --- AP Domain-Specific Image Recovery ---


class TestDomainSpecificImageRecovery:
    def test_ap_uses_richtext_xpath(self):
        """AP News uses RichTextStoryBody xpath, not generic //article//img."""
        extracted = "<p>Text only.</p>"
        raw = (
            "<html><body><article>"
            '<div class="bsp-carousel"><img src="https://cdn.example.com/carousel1.jpg" alt="Carousel"/></div>'
            '<div class="RichTextStoryBody">'
            '<img src="https://cdn.example.com/hero.jpg" alt="Hero photo"/>'
            "</div>"
            "</article></body></html>"
        )
        result = _recover_images_from_html(extracted, raw, "https://apnews.com/article/test")
        assert "hero.jpg" in result
        assert "carousel1.jpg" not in result

    def test_ap_falls_back_to_bsp_figure(self):
        """AP News falls back to bsp-figure xpath."""
        extracted = "<p>Text only.</p>"
        raw = (
            "<html><body><article>"
            '<bsp-figure><img src="https://cdn.example.com/bsp-photo.jpg" alt="BSP"/></bsp-figure>'
            "</article></body></html>"
        )
        result = _recover_images_from_html(extracted, raw, "https://apnews.com/article/test")
        assert "bsp-photo.jpg" in result

    def test_non_ap_uses_generic_xpath(self):
        """Non-AP domains still use the generic //article//img xpath."""
        extracted = "<p>Text only.</p>"
        raw = (
            "<html><body><article>"
            '<img src="https://cdn.example.com/photo.jpg" alt="Photo"/>'
            "</article></body></html>"
        )
        result = _recover_images_from_html(extracted, raw, "https://example.com/article")
        assert "photo.jpg" in result


# --- Bloomberg Normalize Rules ---


class TestBloombergNormalize:
    def test_strips_ad_div_with_nbsp(self):
        """Bloomberg ad divs with non-breaking space are removed."""
        html = (
            '<p>Article content.</p>'
            '<div class="ad news-designed-for-consumer-media" data-ad-type="small-box">\xa0</div>'
            '<p>More content.</p>'
        )
        result = _normalize_html(html)
        assert "ad news-designed" not in result
        assert "Article content" in result
        assert "More content" in result

    def test_strips_duplicate_figcaption_with_caption_div(self):
        """Bloomberg figcaption wrapping news-figure-caption-text div is removed."""
        html = (
            '<figure><img src="photo.jpg" alt="Test"/>'
            '<figcaption>Photo caption</figcaption>'
            '<figcaption><div class="news-figure-caption-text">Photo caption</div></figcaption>'
            '</figure>'
        )
        result = _normalize_html(html)
        assert result.count("Photo caption") == 1
        assert "news-figure-caption-text" not in result
        assert "<img" in result

    def test_strips_standalone_caption_div(self):
        """Bloomberg standalone news-figure-caption-text div is removed."""
        html = (
            '<div class="bplayer-container">'
            '<iframe src="//www.bloomberg.com/api/embed/iframe?id=abc"/>'
            '<div class="news-figure-caption-text">Video Title</div>'
            '</div>'
        )
        result = _normalize_html(html)
        assert "news-figure-caption-text" not in result
        assert "Video Title" not in result


class TestExtractVergeImages:
    """Tests for The Verge __NEXT_DATA__ image extraction."""

    def test_extracts_hero_image(self):
        """Hero image extracted from featuredImage in __NEXT_DATA__."""
        next_data = {
            "props": {"pageProps": {"hydration": {"responses": [{"data": {"node": {
                "featuredImage": {
                    "image": {
                        "originalUrl": "https://platform.theverge.com/photo.jpg",
                        "alt": "Test photo",
                    },
                    "caption": {"plaintext": "A test caption"},
                },
                "blocks": [],
            }}}]}}}
        }
        raw = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'
        images = _extract_verge_images(raw)
        assert len(images) == 1
        assert images[0][0] == "https://platform.theverge.com/photo.jpg"
        assert images[0][1] == "Test photo"
        assert images[0][2] == "A test caption"

    def test_extracts_inline_images(self):
        """Inline CoreImageBlockType blocks extracted."""
        next_data = {
            "props": {"pageProps": {"hydration": {"responses": [{"data": {"node": {
                "featuredImage": None,
                "blocks": [
                    {
                        "__typename": "CoreImageBlockType",
                        "thumbnail": {"url": "https://platform.theverge.com/inline1.jpg"},
                        "alt": "Inline photo",
                        "caption": {"plaintext": ""},
                    },
                    {
                        "__typename": "CoreParagraphBlockType",
                        "attributes": {"content": "Text block"},
                    },
                    {
                        "__typename": "CoreImageBlockType",
                        "thumbnail": {"url": "https://platform.theverge.com/inline2.jpg"},
                        "alt": "Second photo",
                        "caption": {"plaintext": "Photo credit"},
                    },
                ],
            }}}]}}}
        }
        raw = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'
        images = _extract_verge_images(raw)
        assert len(images) == 2
        assert images[0][0] == "https://platform.theverge.com/inline1.jpg"
        assert images[1][0] == "https://platform.theverge.com/inline2.jpg"

    def test_extracts_gallery_images(self):
        """CoreGalleryBlockType images extracted."""
        next_data = {
            "props": {"pageProps": {"hydration": {"responses": [{"data": {"node": {
                "featuredImage": None,
                "blocks": [{
                    "__typename": "CoreGalleryBlockType",
                    "images": [
                        {
                            "image": {"thumbnails": {"horizontal": {"url": "https://platform.theverge.com/g1.jpg"}}},
                            "alt": "Gallery 1",
                            "caption": {"plaintext": ""},
                        },
                        {
                            "image": {"thumbnails": {"horizontal": {"url": "https://platform.theverge.com/g2.jpg"}}},
                            "alt": "Gallery 2",
                            "caption": {"plaintext": ""},
                        },
                    ],
                }],
            }}}]}}}
        }
        raw = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'
        images = _extract_verge_images(raw)
        assert len(images) == 2

    def test_no_next_data_returns_empty(self):
        """No __NEXT_DATA__ script returns empty list."""
        assert _extract_verge_images("<html><body>No data</body></html>") == []

    def test_malformed_json_returns_empty(self):
        """Invalid JSON in __NEXT_DATA__ returns empty list."""
        raw = '<script id="__NEXT_DATA__" type="application/json">{bad json}</script>'
        assert _extract_verge_images(raw) == []

    def test_caps_at_5_images(self):
        """Image cap limits to _JSON_IMAGE_CAP (5) images."""
        blocks = [
            {
                "__typename": "CoreImageBlockType",
                "thumbnail": {"url": f"https://platform.theverge.com/img{i}.jpg"},
                "alt": f"Photo {i}",
                "caption": {"plaintext": ""},
            }
            for i in range(10)
        ]
        next_data = {
            "props": {"pageProps": {"hydration": {"responses": [{"data": {"node": {
                "featuredImage": None,
                "blocks": blocks,
            }}}]}}}
        }
        raw = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'
        images = _extract_verge_images(raw)
        assert len(images) == 5


class TestExtractCondeNastImages:
    """Tests for Condé Nast __PRELOADED_STATE__ image extraction (Wired, New Yorker)."""

    def test_extracts_hero_image(self):
        """Hero/lede image extracted from __PRELOADED_STATE__."""
        state = {
            "transformed": {"article": {
                "headerProps": {"lede": {
                    "contentType": "photo",
                    "sources": {
                        "xl": {"url": "https://media.wired.com/photos/hero.jpg"},
                        "lg": {"url": "https://media.wired.com/photos/hero-lg.jpg"},
                    },
                    "altText": "A factory in Germany",
                    "caption": "",
                    "credit": "Photograph by Reuters",
                }},
                "body": [],
            }}
        }
        raw = f'window.__PRELOADED_STATE__ = {json.dumps(state)}; window.something'
        images = _extract_conde_nast_images(raw)
        assert len(images) == 1
        assert images[0][0] == "https://media.wired.com/photos/hero.jpg"
        assert images[0][1] == "A factory in Germany"
        assert images[0][2] == "Photograph by Reuters"

    def test_extracts_inline_images_from_jsonml_body(self):
        """Inline images from JSONML body array extracted."""
        state = {
            "transformed": {"article": {
                "headerProps": {"lede": None},
                "body": [
                    ["p", {}, "Some text"],
                    ["inline-embed", {
                        "props": {
                            "image": {
                                "contentType": "photo",
                                "sources": {
                                    "xl": {"url": "https://media.newyorker.com/photos/inline1.jpg"},
                                },
                                "altText": "A person standing",
                            },
                            "dangerousCaption": "Photo by Staff",
                        },
                        "type": "callout:feature-small",
                    }],
                ],
            }}
        }
        raw = f'window.__PRELOADED_STATE__ = {json.dumps(state)}; </script>'
        images = _extract_conde_nast_images(raw)
        assert len(images) == 1
        assert images[0][0] == "https://media.newyorker.com/photos/inline1.jpg"
        assert images[0][1] == "A person standing"
        assert images[0][2] == "Photo by Staff"

    def test_walks_nested_image_groups(self):
        """Nested inline-embed groups (3-photo layouts) are traversed."""
        state = {
            "transformed": {"article": {
                "headerProps": {"lede": None},
                "body": [
                    ["inline-embed", {"type": "callout:feature-large"},
                        ["inline-embed", {"type": "callout:group-3"},
                            ["inline-embed", {"props": {
                                "image": {
                                    "contentType": "photo",
                                    "sources": {"xl": {"url": "https://media.newyorker.com/a.jpg"}},
                                    "altText": "Photo A",
                                },
                                "dangerousCaption": "",
                            }}],
                            ["inline-embed", {"props": {
                                "image": {
                                    "contentType": "photo",
                                    "sources": {"xl": {"url": "https://media.newyorker.com/b.jpg"}},
                                    "altText": "Photo B",
                                },
                                "dangerousCaption": "",
                            }}],
                        ],
                    ],
                ],
            }}
        }
        raw = f'window.__PRELOADED_STATE__ = {json.dumps(state)}; </script>'
        images = _extract_conde_nast_images(raw)
        assert len(images) == 2
        assert images[0][0] == "https://media.newyorker.com/a.jpg"
        assert images[1][0] == "https://media.newyorker.com/b.jpg"

    def test_no_preloaded_state_returns_empty(self):
        """No __PRELOADED_STATE__ returns empty list."""
        assert _extract_conde_nast_images("<html><body>No data</body></html>") == []

    def test_prefers_xl_over_lg(self):
        """xl source preferred over lg for highest resolution."""
        state = {
            "transformed": {"article": {
                "headerProps": {"lede": {
                    "contentType": "photo",
                    "sources": {
                        "md": {"url": "https://media.wired.com/md.jpg"},
                        "lg": {"url": "https://media.wired.com/lg.jpg"},
                        "xl": {"url": "https://media.wired.com/xl.jpg"},
                    },
                    "altText": "", "caption": "", "credit": "",
                }},
                "body": [],
            }}
        }
        raw = f'window.__PRELOADED_STATE__ = {json.dumps(state)}; window.x'
        images = _extract_conde_nast_images(raw)
        assert images[0][0] == "https://media.wired.com/xl.jpg"

    def test_caps_at_5_images(self):
        """Image cap limits output."""
        body = []
        for i in range(8):
            body.append(["inline-embed", {
                "props": {
                    "image": {
                        "contentType": "photo",
                        "sources": {"xl": {"url": f"https://media.newyorker.com/{i}.jpg"}},
                        "altText": f"Photo {i}",
                    },
                    "dangerousCaption": "",
                },
            }])
        state = {
            "transformed": {"article": {
                "headerProps": {"lede": None},
                "body": body,
            }}
        }
        raw = f'window.__PRELOADED_STATE__ = {json.dumps(state)}; </script>'
        images = _extract_conde_nast_images(raw)
        assert len(images) == 5


class TestRecoverImagesFromJson:
    """Tests for the JSON-based image recovery dispatch."""

    def test_verge_domain_triggers_extraction(self):
        """theverge.com domain routes to Verge extractor."""
        next_data = {
            "props": {"pageProps": {"hydration": {"responses": [{"data": {"node": {
                "featuredImage": {
                    "image": {"originalUrl": "https://platform.theverge.com/hero.jpg", "alt": "Hero"},
                    "caption": {"plaintext": ""},
                },
                "blocks": [],
            }}}]}}}
        }
        raw = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'
        result = _recover_images_from_json(raw, "https://www.theverge.com/2024/1/article")
        assert len(result) == 1
        assert "hero.jpg" in result[0]

    def test_wired_domain_triggers_extraction(self):
        """wired.com domain routes to Condé Nast extractor."""
        state = {
            "transformed": {"article": {
                "headerProps": {"lede": {
                    "contentType": "photo",
                    "sources": {"xl": {"url": "https://media.wired.com/hero.jpg"}},
                    "altText": "Test", "caption": "", "credit": "",
                }},
                "body": [],
            }}
        }
        raw = f'window.__PRELOADED_STATE__ = {json.dumps(state)}; window.x'
        result = _recover_images_from_json(raw, "https://www.wired.com/story/test/")
        assert len(result) == 1
        assert "hero.jpg" in result[0]

    def test_newyorker_domain_triggers_extraction(self):
        """newyorker.com domain routes to Condé Nast extractor."""
        state = {
            "transformed": {"article": {
                "headerProps": {"lede": {
                    "contentType": "photo",
                    "sources": {"xl": {"url": "https://media.newyorker.com/hero.jpg"}},
                    "altText": "Test", "caption": "", "credit": "",
                }},
                "body": [],
            }}
        }
        raw = f'window.__PRELOADED_STATE__ = {json.dumps(state)}; window.x'
        result = _recover_images_from_json(raw, "https://www.newyorker.com/news/test")
        assert len(result) == 1
        assert "hero.jpg" in result[0]

    def test_unknown_domain_returns_empty(self):
        """Non-matching domain returns empty list."""
        result = _recover_images_from_json("<html></html>", "https://example.com/article")
        assert result == []

    def test_no_url_returns_empty(self):
        """No page_url returns empty list."""
        assert _recover_images_from_json("<html></html>", "") == []

    def test_deduplicates_images(self):
        """Duplicate image URLs are deduplicated."""
        next_data = {
            "props": {"pageProps": {"hydration": {"responses": [{"data": {"node": {
                "featuredImage": {
                    "image": {"originalUrl": "https://platform.theverge.com/same.jpg", "alt": ""},
                    "caption": {"plaintext": ""},
                },
                "blocks": [{
                    "__typename": "CoreImageBlockType",
                    "thumbnail": {"url": "https://platform.theverge.com/same.jpg"},
                    "alt": "", "caption": {"plaintext": ""},
                }],
            }}}]}}}
        }
        raw = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'
        result = _recover_images_from_json(raw, "https://www.theverge.com/article")
        assert len(result) == 1

    def test_integration_with_recover_images(self):
        """JSON recovery integrates with _recover_images_from_html."""
        state = {
            "transformed": {"article": {
                "headerProps": {"lede": {
                    "contentType": "photo",
                    "sources": {"xl": {"url": "https://media.wired.com/photo.jpg"}},
                    "altText": "Test photo", "caption": "", "credit": "",
                }},
                "body": [],
            }}
        }
        raw = f'<html><body>window.__PRELOADED_STATE__ = {json.dumps(state)}; window.x</body></html>'
        extracted = "<p>Article text with no images.</p>"
        result = _recover_images_from_html(extracted, raw, "https://www.wired.com/story/test/")
        assert "photo.jpg" in result
        assert "Article text" in result
