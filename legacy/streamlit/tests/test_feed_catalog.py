"""Tests for the curated feed catalog service."""

from __future__ import annotations

import pytest

from web.services.feed_catalog import (
    get_all_feeds,
    get_bundles,
    get_categories,
    get_feeds_for_bundle,
    validate_rss_url,
)


# --- TestLoadCatalog (integration — reads real YAML file) ---


class TestLoadCatalog:
    def test_loads_real_catalog_file(self):
        """The actual feed_catalog.yaml is valid and parseable."""
        bundles = get_bundles()
        categories = get_categories()
        assert isinstance(bundles, list)
        assert isinstance(categories, list)

    def test_catalog_has_bundles(self):
        """Real catalog has at least 3 bundles."""
        assert len(get_bundles()) >= 3

    def test_catalog_has_categories(self):
        """Real catalog has at least 7 categories."""
        assert len(get_categories()) >= 7


# --- TestGetBundles ---


class TestGetBundles:
    def test_returns_list_of_dicts(self):
        """Each bundle has name, description, and feeds keys."""
        for bundle in get_bundles():
            assert "name" in bundle
            assert "description" in bundle
            assert "feeds" in bundle
            assert isinstance(bundle["feeds"], list)

    def test_bundles_have_valid_feed_ids(self):
        """All feed IDs in bundles exist in the categories."""
        all_feeds = get_all_feeds()
        for bundle in get_bundles():
            for feed_id in bundle["feeds"]:
                assert feed_id in all_feeds, f"Bundle '{bundle['name']}' references unknown feed ID '{feed_id}'"


# --- TestGetCategories ---


class TestGetCategories:
    def test_returns_list_of_dicts(self):
        """Each category has name and feeds keys."""
        for cat in get_categories():
            assert "name" in cat
            assert "feeds" in cat
            assert isinstance(cat["feeds"], list)

    def test_category_feeds_have_required_keys(self):
        """Each feed has id, name, url, and description."""
        for cat in get_categories():
            for feed in cat["feeds"]:
                assert "id" in feed
                assert "name" in feed
                assert "url" in feed
                assert "description" in feed


# --- TestGetAllFeeds ---


class TestGetAllFeeds:
    def test_returns_flat_dict(self):
        """Returns a dict keyed by feed ID."""
        feeds = get_all_feeds()
        assert isinstance(feeds, dict)
        assert len(feeds) > 0

    def test_all_feeds_have_required_keys(self):
        """Each feed has id, name, url, description."""
        for feed_id, feed in get_all_feeds().items():
            assert feed["id"] == feed_id
            assert "name" in feed
            assert "url" in feed

    def test_no_duplicate_ids(self):
        """Feed IDs are unique across categories."""
        seen = set()
        for cat in get_categories():
            for feed in cat["feeds"]:
                assert feed["id"] not in seen, f"Duplicate feed ID: {feed['id']}"
                seen.add(feed["id"])


# --- TestGetFeedsForBundle ---


class TestGetFeedsForBundle:
    def test_returns_feeds_for_known_bundle(self):
        """Returns a list of feed dicts for a known bundle name."""
        bundles = get_bundles()
        bundle_name = bundles[0]["name"]
        feeds = get_feeds_for_bundle(bundle_name)
        assert len(feeds) > 0
        for feed in feeds:
            assert "id" in feed
            assert "url" in feed

    def test_returns_empty_for_unknown_bundle(self):
        """Unknown bundle name returns empty list."""
        assert get_feeds_for_bundle("Nonexistent Bundle") == []

    def test_feed_count_matches_bundle(self):
        """Number of returned feeds matches bundle's feed ID list."""
        for bundle in get_bundles():
            feeds = get_feeds_for_bundle(bundle["name"])
            assert len(feeds) == len(bundle["feeds"])


# --- TestValidateRssUrl ---


class TestValidateRssUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/rss",
            "http://feeds.example.org/news",
            "https://sub.domain.co/feed.xml",
            "https://example.com/rss?format=xml",
        ],
    )
    def test_valid_urls(self, url):
        """Valid RSS URLs return True."""
        assert validate_rss_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "not-a-url",
            "ftp://example.com",
            "https://nodot",
            "   ",
        ],
    )
    def test_invalid_urls(self, url):
        """Invalid URLs return False."""
        assert validate_rss_url(url) is False
