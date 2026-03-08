"""Tests for POST /build endpoint."""

from __future__ import annotations

import base64
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest

from paper_boy.feeds import Article, Section


@dataclass
class _FakeBuildResult:
    epub_path: str
    sections: list
    total_articles: int


def _make_fake_epub(tmp_dir: str) -> str:
    """Create a small fake EPUB file and return its path."""
    path = os.path.join(tmp_dir, "test.epub")
    with open(path, "wb") as f:
        f.write(b"PK" + b"\x00" * 500)  # ~502 bytes
    return path


class TestBuildEndpoint:
    """Tests for the /build API route."""

    @patch("api.routes.build.build_newspaper")
    def test_build_returns_epub_base64(self, mock_build, api_client, auth_header, make_article):
        """POST /build with valid feeds returns success with EPUB data."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            epub_path = _make_fake_epub(tmp_dir)
            articles = [make_article(title=f"Headline {i}") for i in range(3)]
            mock_build.return_value = _FakeBuildResult(
                epub_path=epub_path,
                sections=[Section(name="Tech", articles=articles)],
                total_articles=3,
            )

            resp = api_client.post(
                "/build",
                json={"feeds": [{"name": "Test", "url": "https://example.com/rss"}]},
                headers=auth_header,
            )

        data = resp.json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert data["epub_base64"]
        assert data["total_articles"] == 3
        assert len(data["sections"]) == 1
        assert data["sections"][0]["name"] == "Tech"
        assert "Headline 0" in data["sections"][0]["headlines"]

    def test_build_empty_feeds_returns_error(self, api_client, auth_header):
        """POST /build with empty feeds list returns success=False."""
        resp = api_client.post(
            "/build",
            json={"feeds": []},
            headers=auth_header,
        )
        data = resp.json()
        assert data["success"] is False
        assert data["error"] == "No feeds provided"

    def test_build_missing_feeds_returns_422(self, api_client, auth_header):
        """POST /build without feeds field returns validation error."""
        resp = api_client.post(
            "/build",
            json={"title": "Test"},
            headers=auth_header,
        )
        assert resp.status_code == 422

    @patch("api.routes.build.build_newspaper", side_effect=RuntimeError("No articles fetched"))
    def test_build_exception_returns_error(self, mock_build, api_client, auth_header):
        """Build exceptions are caught and returned as success=False."""
        resp = api_client.post(
            "/build",
            json={"feeds": [{"name": "Test", "url": "https://example.com/rss"}]},
            headers=auth_header,
        )
        data = resp.json()
        assert data["success"] is False
        assert "Newspaper build failed" in data["error"]

    @patch("api.routes.build.build_newspaper")
    def test_build_file_size_kb(self, mock_build, api_client, auth_header, make_article):
        """Small EPUBs get KB file size label."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            epub_path = _make_fake_epub(tmp_dir)
            mock_build.return_value = _FakeBuildResult(
                epub_path=epub_path,
                sections=[Section(name="News", articles=[make_article()])],
                total_articles=1,
            )

            resp = api_client.post(
                "/build",
                json={"feeds": [{"name": "Test", "url": "https://example.com/rss"}]},
                headers=auth_header,
            )

        data = resp.json()
        assert "KB" in data["file_size"]
        assert data["file_size_bytes"] > 0

    def test_build_applies_request_defaults(self, api_client, auth_header):
        """Default values from BuildRequest model are applied."""
        # This tests that Pydantic defaults work — the request with
        # only feeds should still be accepted (title, language, etc. default).
        with patch("api.routes.build.build_newspaper") as mock_build:
            with tempfile.TemporaryDirectory() as tmp_dir:
                epub_path = _make_fake_epub(tmp_dir)
                mock_build.return_value = _FakeBuildResult(
                    epub_path=epub_path, sections=[], total_articles=0,
                )

                resp = api_client.post(
                    "/build",
                    json={"feeds": [{"name": "F", "url": "https://example.com/rss"}]},
                    headers=auth_header,
                )

            assert resp.status_code == 200
            # Verify the config was built with defaults
            call_args = mock_build.call_args
            config = call_args[0][0]
            assert config.newspaper.title == "Morning Digest"
            assert config.newspaper.language == "en"
            assert config.delivery.device == "kobo"
