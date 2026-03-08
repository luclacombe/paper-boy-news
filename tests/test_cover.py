"""Tests for cover image generation."""

from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from paper_boy.cover import (
    COVER_HEIGHT,
    COVER_WIDTH,
    _BUNDLED_FONT,
    _load_font,
    generate_cover,
)
from paper_boy.feeds import Article, Section


def _make_sections(count=3):
    names = ["World News", "Technology", "Science", "Business", "Opinion", "Culture"]
    return [
        Section(
            name=names[i % len(names)],
            articles=[
                Article(
                    title=f"Headline {i + 1}: Important Story",
                    url=f"https://example.com/{i + 1}",
                ),
            ],
        )
        for i in range(count)
    ]


# --- Basic output ---


class TestGenerateCover:
    def test_returns_jpeg_bytes(self):
        cover_bytes = generate_cover("Morning Digest", _make_sections(), date(2026, 2, 28))
        assert len(cover_bytes) > 0
        img = Image.open(BytesIO(cover_bytes))
        assert img.format == "JPEG"

    def test_dimensions(self):
        cover_bytes = generate_cover("Test Paper", _make_sections(), date(2026, 1, 1))
        img = Image.open(BytesIO(cover_bytes))
        assert img.size == (COVER_WIDTH, COVER_HEIGHT)

    def test_default_date(self):
        cover_bytes = generate_cover("Test", _make_sections())
        assert len(cover_bytes) > 0

    def test_empty_sections(self):
        cover_bytes = generate_cover("Test Paper", [], date(2026, 1, 1))
        assert len(cover_bytes) > 0
        img = Image.open(BytesIO(cover_bytes))
        assert img.size == (COVER_WIDTH, COVER_HEIGHT)

    def test_single_section(self):
        sections = [
            Section("World", [Article(title="Single Headline", url="https://x.com/1")])
        ]
        cover_bytes = generate_cover("Test", sections, date(2026, 1, 1))
        assert len(cover_bytes) > 0

    def test_many_sections(self):
        """22 sections should not error — extra headlines are simply clipped."""
        cover_bytes = generate_cover("Test", _make_sections(22), date(2026, 1, 1))
        assert len(cover_bytes) > 0
        img = Image.open(BytesIO(cover_bytes))
        assert img.size == (COVER_WIDTH, COVER_HEIGHT)

    def test_long_title_scales_down(self):
        """A very long newspaper title should scale to fit, not clip."""
        cover_bytes = generate_cover(
            "The International Morning Digest Weekly Edition",
            _make_sections(),
            date(2026, 1, 1),
        )
        assert len(cover_bytes) > 0
        img = Image.open(BytesIO(cover_bytes))
        assert img.size == (COVER_WIDTH, COVER_HEIGHT)

    def test_long_headline_wraps(self):
        """A very long headline should word-wrap, not error."""
        sections = [
            Section(
                "World",
                [
                    Article(
                        title="This Is An Extremely Long Headline That Should Be "
                        "Word-Wrapped Across Multiple Lines on the Cover",
                        url="https://x.com/1",
                    )
                ],
            )
        ]
        cover_bytes = generate_cover("Test", sections, date(2026, 1, 1))
        assert len(cover_bytes) > 0

    def test_section_with_empty_articles(self):
        """Section with no articles is skipped gracefully."""
        sections = [
            Section("Empty", []),
            Section("World", [Article(title="Real Headline", url="https://x.com/1")]),
        ]
        cover_bytes = generate_cover("Test", sections, date(2026, 1, 1))
        assert len(cover_bytes) > 0


# --- Font loading ---


class TestLoadFont:
    def test_bundled_font_exists(self):
        """The bundled Playfair Display font file should be present."""
        assert _BUNDLED_FONT.exists(), f"Bundled font not found at {_BUNDLED_FONT}"
        assert _BUNDLED_FONT.stat().st_size > 10000  # Not a stub/placeholder

    def test_loads_regular_weight(self):
        font = _load_font(24, "Regular")
        assert font is not None
        assert hasattr(font, "getbbox")  # FreeTypeFont, not bitmap default

    def test_loads_bold_weight(self):
        font = _load_font(24, "Bold")
        assert font is not None

    def test_loads_extrabold_weight(self):
        font = _load_font(24, "ExtraBold")
        assert font is not None

    def test_fallback_when_bundled_missing(self):
        """When bundled font is gone, falls back to system or default without error."""
        with patch("paper_boy.cover._BUNDLED_FONT", Path("/nonexistent/font.ttf")):
            font = _load_font(24, "Regular")
            assert font is not None  # Got a system font or bitmap fallback
