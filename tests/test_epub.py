"""Tests for EPUB generation."""

import tempfile
import zipfile
from datetime import date
from pathlib import Path

from ebooklib import epub

from paper_boy.config import Config, DeliveryConfig, FeedConfig, NewspaperConfig
from paper_boy.epub import build_epub
from paper_boy.feeds import Article, Section


def _make_config():
    return Config(
        newspaper=NewspaperConfig(title="Test Digest"),
        feeds=[FeedConfig(name="News", url="https://example.com/rss")],
        delivery=DeliveryConfig(method="local"),
    )


def _make_sections():
    return [
        Section(
            name="World",
            articles=[
                Article(
                    title="Test Article One",
                    url="https://example.com/1",
                    author="Alice",
                    date="2026-02-28",
                    html_content="<p>This is the first test article with some content.</p>",
                ),
                Article(
                    title="Test Article Two",
                    url="https://example.com/2",
                    author="Bob",
                    html_content="<p>Second article body text here.</p>",
                ),
            ],
        ),
        Section(
            name="Tech",
            articles=[
                Article(
                    title="Tech Article",
                    url="https://example.com/3",
                    html_content="<p>Technology news content.</p>",
                ),
            ],
        ),
    ]


def test_build_epub_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        result = build_epub(_make_sections(), _make_config(), date(2026, 2, 28), output)
        assert result.exists()
        assert result.suffix == ".epub"


def test_build_epub_is_valid_zip():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(_make_sections(), _make_config(), date(2026, 2, 28), output)
        assert zipfile.is_zipfile(output)


def test_build_epub_contains_articles():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(_make_sections(), _make_config(), date(2026, 2, 28), output)

        book = epub.read_epub(str(output))
        items = list(book.get_items_of_type(9))  # XHTML documents
        # front_page + 2 section dividers + 3 articles = 6
        # Plus nav and other items — just check we have enough
        assert len(items) >= 5


def test_build_epub_has_cover():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(_make_sections(), _make_config(), date(2026, 2, 28), output)

        # Check that the cover image exists in the EPUB zip
        with zipfile.ZipFile(output) as z:
            names = z.namelist()
            cover_files = [n for n in names if "cover" in n.lower() and n.endswith((".jpg", ".jpeg"))]
            assert len(cover_files) >= 1


def test_build_epub_has_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(_make_sections(), _make_config(), date(2026, 2, 28), output)

        book = epub.read_epub(str(output))
        title = book.get_metadata("DC", "title")
        assert title
        assert "Test Digest" in title[0][0]


def test_build_epub_has_series_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(_make_sections(), _make_config(), date(2026, 2, 28), output)

        # Read the OPF content directly from the zip to check calibre:series
        with zipfile.ZipFile(output) as z:
            opf_files = [n for n in z.namelist() if n.endswith(".opf")]
            assert opf_files
            opf_content = z.read(opf_files[0]).decode("utf-8")
            assert "calibre:series" in opf_content
            assert "Test Digest" in opf_content


def test_build_epub_default_output_name():
    with tempfile.TemporaryDirectory() as tmpdir:
        import os
        original = os.getcwd()
        try:
            os.chdir(tmpdir)
            result = build_epub(_make_sections(), _make_config(), date(2026, 2, 28))
            assert result.name == "paper-boy-2026-02-28.epub"
            assert result.exists()
        finally:
            os.chdir(original)


def test_build_epub_nav_not_in_spine():
    """Nav document should not appear in the reading spine."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(_make_sections(), _make_config(), date(2026, 2, 28), output)
        with zipfile.ZipFile(output) as z:
            opf_files = [n for n in z.namelist() if n.endswith(".opf")]
            opf_content = z.read(opf_files[0]).decode("utf-8")
            import re
            spine_refs = re.findall(r'<itemref idref="([^"]+)"', opf_content)
            assert "nav" not in spine_refs
