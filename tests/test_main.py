"""Tests for the main orchestration module."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from paper_boy.cache import ContentCache
from paper_boy.main import BuildResult, build_and_deliver, build_newspaper


class TestBuildResult:
    def test_dataclass_fields(self):
        """BuildResult has epub_path, sections, and total_articles."""
        result = BuildResult(
            epub_path=Path("/tmp/test.epub"),
            sections=[],
            total_articles=0,
        )
        assert result.epub_path == Path("/tmp/test.epub")
        assert result.sections == []
        assert result.total_articles == 0

    def test_instantiation_with_data(self, make_sections):
        """BuildResult stores sections and article counts correctly."""
        sections = make_sections(num_sections=2, articles_per_section=3)
        result = BuildResult(
            epub_path=Path("/tmp/paper.epub"),
            sections=sections,
            total_articles=6,
        )
        assert len(result.sections) == 2
        assert result.total_articles == 6


class TestBuildNewspaper:
    @patch("paper_boy.main.build_epub")
    @patch("paper_boy.main.fetch_feeds")
    def test_returns_build_result(self, mock_fetch, mock_epub, local_config, make_sections):
        """build_newspaper returns a BuildResult with correct fields."""
        sections = make_sections(num_sections=2, articles_per_section=3)
        mock_fetch.return_value = sections
        mock_epub.return_value = Path("/tmp/test.epub")

        result = build_newspaper(local_config)
        assert isinstance(result, BuildResult)
        assert result.epub_path == Path("/tmp/test.epub")
        assert result.total_articles == 6

    @patch("paper_boy.main.build_epub")
    @patch("paper_boy.main.fetch_feeds")
    def test_calls_fetch_feeds_with_config(self, mock_fetch, mock_epub, local_config, make_sections):
        """fetch_feeds is called with the provided config."""
        mock_fetch.return_value = make_sections()
        mock_epub.return_value = Path("/tmp/test.epub")

        build_newspaper(local_config)
        mock_fetch.assert_called_once_with(local_config, cache=None)

    @patch("paper_boy.main.build_epub")
    @patch("paper_boy.main.fetch_feeds")
    def test_calls_build_epub_with_correct_args(
        self, mock_fetch, mock_epub, local_config, make_sections
    ):
        """build_epub receives sections, config, date, and output_path."""
        sections = make_sections()
        mock_fetch.return_value = sections
        mock_epub.return_value = Path("/tmp/test.epub")
        test_date = date(2026, 3, 1)

        build_newspaper(local_config, output_path="/tmp/out.epub", issue_date=test_date)

        mock_epub.assert_called_once_with(sections, local_config, test_date, "/tmp/out.epub")

    @patch("paper_boy.main.fetch_feeds")
    def test_raises_runtime_error_when_no_articles(self, mock_fetch, local_config):
        """RuntimeError raised when all sections have zero articles."""
        mock_fetch.return_value = []

        with pytest.raises(RuntimeError, match="No articles were extracted"):
            build_newspaper(local_config)

    @patch("paper_boy.main.build_epub")
    @patch("paper_boy.main.fetch_feeds")
    def test_uses_today_when_no_date(self, mock_fetch, mock_epub, local_config, make_sections):
        """When issue_date is None, date.today() is used."""
        mock_fetch.return_value = make_sections()
        mock_epub.return_value = Path("/tmp/test.epub")

        build_newspaper(local_config)

        call_args = mock_epub.call_args[0]
        assert call_args[2] == date.today()

    @patch("paper_boy.main.build_epub")
    @patch("paper_boy.main.fetch_feeds")
    def test_passes_custom_date(self, mock_fetch, mock_epub, local_config, make_sections):
        """Custom issue_date is forwarded to build_epub."""
        mock_fetch.return_value = make_sections()
        mock_epub.return_value = Path("/tmp/test.epub")
        custom_date = date(2025, 12, 25)

        build_newspaper(local_config, issue_date=custom_date)

        call_args = mock_epub.call_args[0]
        assert call_args[2] == custom_date

    @patch("paper_boy.main.build_epub")
    @patch("paper_boy.main.fetch_feeds")
    def test_total_articles_counts_all_sections(
        self, mock_fetch, mock_epub, local_config, make_sections
    ):
        """total_articles sums articles across all sections."""
        sections = make_sections(num_sections=3, articles_per_section=4)
        mock_fetch.return_value = sections
        mock_epub.return_value = Path("/tmp/test.epub")

        result = build_newspaper(local_config)
        assert result.total_articles == 12

    @patch("paper_boy.main.build_epub")
    @patch("paper_boy.main.fetch_feeds")
    def test_passes_cache_to_fetch_feeds(
        self, mock_fetch, mock_epub, local_config, make_sections
    ):
        """Cache object is forwarded to fetch_feeds."""
        mock_fetch.return_value = make_sections()
        mock_epub.return_value = Path("/tmp/test.epub")
        cache = ContentCache()

        build_newspaper(local_config, cache=cache)
        mock_fetch.assert_called_once_with(local_config, cache=cache)


class TestBuildAndDeliver:
    @patch("paper_boy.main.deliver")
    @patch("paper_boy.main.build_epub")
    @patch("paper_boy.main.fetch_feeds")
    def test_calls_build_then_deliver(
        self, mock_fetch, mock_epub, mock_deliver, local_config, make_sections
    ):
        """build_and_deliver calls build_newspaper then deliver."""
        mock_fetch.return_value = make_sections()
        mock_epub.return_value = Path("/tmp/test.epub")

        build_and_deliver(local_config)

        mock_fetch.assert_called_once()
        mock_epub.assert_called_once()
        mock_deliver.assert_called_once()

    @patch("paper_boy.main.deliver")
    @patch("paper_boy.main.build_epub")
    @patch("paper_boy.main.fetch_feeds")
    def test_passes_epub_path_to_deliver(
        self, mock_fetch, mock_epub, mock_deliver, local_config, make_sections
    ):
        """deliver receives the epub_path from build_newspaper result."""
        mock_fetch.return_value = make_sections()
        epub_path = Path("/tmp/test.epub")
        mock_epub.return_value = epub_path

        build_and_deliver(local_config)

        mock_deliver.assert_called_once_with(epub_path, local_config, article_count=4, source_count=2)

    @patch("paper_boy.main.deliver")
    @patch("paper_boy.main.build_epub")
    @patch("paper_boy.main.fetch_feeds")
    def test_returns_build_result(
        self, mock_fetch, mock_epub, mock_deliver, local_config, make_sections
    ):
        """Return value is a BuildResult from build_newspaper."""
        mock_fetch.return_value = make_sections()
        mock_epub.return_value = Path("/tmp/test.epub")

        result = build_and_deliver(local_config)
        assert isinstance(result, BuildResult)

    @patch("paper_boy.main.deliver", side_effect=RuntimeError("delivery failed"))
    @patch("paper_boy.main.build_epub")
    @patch("paper_boy.main.fetch_feeds")
    def test_deliver_failure_propagates(
        self, mock_fetch, mock_epub, mock_deliver, local_config, make_sections
    ):
        """Exception in deliver() propagates to caller."""
        mock_fetch.return_value = make_sections()
        mock_epub.return_value = Path("/tmp/test.epub")

        with pytest.raises(RuntimeError, match="delivery failed"):
            build_and_deliver(local_config)
