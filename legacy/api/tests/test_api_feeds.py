"""Tests for POST /feeds/validate endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestFeedValidateEndpoint:
    """Tests for the /feeds/validate API route."""

    @patch("api.routes.feeds.feedparser.parse")
    def test_valid_feed_returns_name(self, mock_parse, api_client, auth_header):
        """Valid RSS feed returns valid=True and feed title."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[{"title": "Article 1"}],
            feed={"title": "Ars Technica"},
        )

        resp = api_client.post(
            "/feeds/validate",
            json={"url": "https://feeds.arstechnica.com/arstechnica/index"},
            headers=auth_header,
        )
        data = resp.json()
        assert data["valid"] is True
        assert data["name"] == "Ars Technica"

    @patch("api.routes.feeds.feedparser.parse")
    def test_bozo_with_no_entries_returns_invalid(self, mock_parse, api_client, auth_header):
        """Bozo feed with no entries returns valid=False with error."""
        mock_parse.return_value = MagicMock(
            bozo=True,
            entries=[],
            bozo_exception=Exception("not well-formed"),
        )

        resp = api_client.post(
            "/feeds/validate",
            json={"url": "https://example.com/bad"},
            headers=auth_header,
        )
        data = resp.json()
        assert data["valid"] is False
        assert data["error"]

    @patch("api.routes.feeds.feedparser.parse")
    def test_empty_feed_returns_no_articles(self, mock_parse, api_client, auth_header):
        """Feed with zero entries returns valid=False."""
        mock_parse.return_value = MagicMock(
            bozo=False,
            entries=[],
        )

        resp = api_client.post(
            "/feeds/validate",
            json={"url": "https://example.com/empty"},
            headers=auth_header,
        )
        data = resp.json()
        assert data["valid"] is False
        assert "No articles" in data["error"]

    @patch("api.routes.feeds.feedparser.parse")
    def test_bozo_with_entries_still_valid(self, mock_parse, api_client, auth_header):
        """Bozo feed that has entries is treated as valid."""
        mock_parse.return_value = MagicMock(
            bozo=True,
            entries=[{"title": "Article"}],
            feed={"title": "Quirky Feed"},
        )

        resp = api_client.post(
            "/feeds/validate",
            json={"url": "https://example.com/quirky"},
            headers=auth_header,
        )
        data = resp.json()
        assert data["valid"] is True
        assert data["name"] == "Quirky Feed"

    @patch("api.routes.feeds.feedparser.parse", side_effect=Exception("network error"))
    def test_exception_returns_invalid(self, mock_parse, api_client, auth_header):
        """Exceptions in feedparser return valid=False."""
        resp = api_client.post(
            "/feeds/validate",
            json={"url": "https://example.com/broken"},
            headers=auth_header,
        )
        data = resp.json()
        assert data["valid"] is False
        assert "Could not validate this feed" in data["error"]
