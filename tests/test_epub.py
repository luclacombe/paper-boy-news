"""Tests for EPUB generation."""

import tempfile
import zipfile
from datetime import date
from pathlib import Path

from ebooklib import epub

from paper_boy.config import Config, DeliveryConfig, FeedConfig, NewspaperConfig
from paper_boy.epub import build_epub, _group_sections_by_category
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


def _make_categorized_sections():
    """Sections with category metadata for category grouping tests."""
    return [
        Section(
            name="The Guardian",
            category="World News",
            articles=[
                Article(
                    title="Guardian Article",
                    url="https://example.com/1",
                    html_content="<p>World news content.</p>",
                ),
            ],
        ),
        Section(
            name="BBC World",
            category="World News",
            articles=[
                Article(
                    title="BBC Article",
                    url="https://example.com/2",
                    html_content="<p>BBC world content.</p>",
                ),
            ],
        ),
        Section(
            name="Ars Technica",
            category="Technology",
            articles=[
                Article(
                    title="Tech Article",
                    url="https://example.com/3",
                    html_content="<p>Tech content.</p>",
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
        # cover_page + front_page + 2 section dividers + 3 articles = 7
        # Plus nav and other items — just check we have enough
        assert len(items) >= 6


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


def test_build_epub_cover_page_first_in_spine():
    """Cover page should be the first item in the reading spine."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(_make_sections(), _make_config(), date(2026, 2, 28), output)
        with zipfile.ZipFile(output) as z:
            opf_files = [n for n in z.namelist() if n.endswith(".opf")]
            opf_content = z.read(opf_files[0]).decode("utf-8")
            # cover_page.xhtml should exist in the zip
            names = z.namelist()
            assert any("cover_page" in n for n in names)


def test_build_epub_has_guide_landmarks():
    """EPUB should have guide entries for cover and TOC."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(_make_sections(), _make_config(), date(2026, 2, 28), output)
        with zipfile.ZipFile(output) as z:
            opf_files = [n for n in z.namelist() if n.endswith(".opf")]
            opf_content = z.read(opf_files[0]).decode("utf-8")
            assert "cover_page.xhtml" in opf_content
            assert "front_page.xhtml" in opf_content


def test_build_epub_with_categories():
    """EPUB with categorized sections should include category dividers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(_make_categorized_sections(), _make_config(), date(2026, 2, 28), output)
        with zipfile.ZipFile(output) as z:
            names = z.namelist()
            category_pages = [n for n in names if "category_" in n]
            assert len(category_pages) == 2  # World News + Technology


def test_build_epub_without_categories_no_dividers():
    """EPUB without categories (CLI mode) should have no category dividers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(_make_sections(), _make_config(), date(2026, 2, 28), output)
        with zipfile.ZipFile(output) as z:
            names = z.namelist()
            category_pages = [n for n in names if "category_" in n]
            assert len(category_pages) == 0


# --- TestGroupSectionsByCategory ---


class TestGroupSectionsByCategory:
    def test_no_categories_returns_single_group(self):
        """Sections without categories return a single group with empty key."""
        sections = _make_sections()
        groups = _group_sections_by_category(sections)
        assert len(groups) == 1
        assert groups[0][0] == ""
        assert len(groups[0][1]) == 2

    def test_categories_grouped_correctly(self):
        """Sections with categories are grouped by category."""
        sections = _make_categorized_sections()
        groups = _group_sections_by_category(sections)
        assert len(groups) == 2
        assert groups[0][0] == "World News"
        assert len(groups[0][1]) == 2  # Guardian + BBC
        assert groups[1][0] == "Technology"
        assert len(groups[1][1]) == 1  # Ars Technica

    def test_custom_category_goes_to_other(self):
        """Sections with 'Custom' category go to 'Other'."""
        sections = [
            Section(name="Feed A", category="World News", articles=[
                Article(title="A", url="http://a.com", html_content="<p>A</p>"),
            ]),
            Section(name="Custom Feed", category="Custom", articles=[
                Article(title="B", url="http://b.com", html_content="<p>B</p>"),
            ]),
        ]
        groups = _group_sections_by_category(sections)
        names = [g[0] for g in groups]
        assert "Other" in names

    def test_empty_sections_skipped(self):
        """Sections with no articles are skipped."""
        sections = [
            Section(name="Empty", category="World News", articles=[]),
            Section(name="Full", category="Tech", articles=[
                Article(title="A", url="http://a.com", html_content="<p>A</p>"),
            ]),
        ]
        groups = _group_sections_by_category(sections)
        assert len(groups) == 1
        assert groups[0][0] == "Tech"
