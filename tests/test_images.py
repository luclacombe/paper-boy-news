"""Tests for article image extraction, optimization, and EPUB embedding."""

import tempfile
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image

from paper_boy.config import Config, DeliveryConfig, FeedConfig, NewspaperConfig
from paper_boy.epub import build_epub
from paper_boy.feeds import (
    IMG_PLACEHOLDER_PREFIX,
    Article,
    ArticleImage,
    Section,
    _convert_graphics_to_imgs,
    _process_article_images,
    _should_skip_image,
    optimize_image,
)


def _make_test_image(width: int = 400, height: int = 300, color: str = "red") -> bytes:
    """Create a test JPEG image of the given size."""
    img = Image.new("RGB", (width, height), color)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _make_config(include_images: bool = True) -> Config:
    return Config(
        newspaper=NewspaperConfig(
            title="Test Digest",
            include_images=include_images,
            image_max_width=800,
            image_max_height=1200,
            image_quality=80,
            image_min_dimension=100,
        ),
        feeds=[FeedConfig(name="News", url="https://example.com/rss")],
        delivery=DeliveryConfig(method="local"),
    )


# --- optimize_image tests ---


class TestOptimizeImage:
    def test_returns_jpeg_bytes(self):
        raw = _make_test_image(400, 300)
        result = optimize_image(raw)
        assert result is not None
        img = Image.open(BytesIO(result))
        assert img.format == "JPEG"

    def test_resizes_wide_image(self):
        raw = _make_test_image(2000, 1000)
        result = optimize_image(raw, max_width=800)
        assert result is not None
        img = Image.open(BytesIO(result))
        assert img.width <= 800

    def test_resizes_tall_image(self):
        raw = _make_test_image(600, 3000)
        result = optimize_image(raw, max_height=1200)
        assert result is not None
        img = Image.open(BytesIO(result))
        assert img.height <= 1200

    def test_skips_tiny_image(self):
        raw = _make_test_image(50, 50)
        result = optimize_image(raw, min_dimension=100)
        assert result is None

    def test_converts_rgba_to_rgb(self):
        img = Image.new("RGBA", (200, 200), (255, 0, 0, 128))
        buf = BytesIO()
        img.save(buf, format="PNG")
        result = optimize_image(buf.getvalue())
        assert result is not None
        out = Image.open(BytesIO(result))
        assert out.mode == "RGB"

    def test_invalid_data_returns_none(self):
        result = optimize_image(b"not an image")
        assert result is None

    def test_preserves_small_image_dimensions(self):
        raw = _make_test_image(200, 150)
        result = optimize_image(raw, max_width=800)
        assert result is not None
        img = Image.open(BytesIO(result))
        assert img.width == 200
        assert img.height == 150


# --- _should_skip_image tests ---


class TestShouldSkipImage:
    def test_skips_ad_domains(self):
        assert _should_skip_image("https://ads.example.com/img.jpg")
        assert _should_skip_image("https://www.doubleclick.net/pixel.gif")

    def test_skips_tracking_paths(self):
        assert _should_skip_image("https://example.com/ads/banner.jpg")
        assert _should_skip_image("https://example.com/tracking/pixel.gif")

    def test_skips_logo_patterns(self):
        assert _should_skip_image("https://example.com/images/logo.png")
        assert _should_skip_image("https://example.com/images/social-icon.png")

    def test_allows_normal_images(self):
        assert not _should_skip_image("https://example.com/photos/article-hero.jpg")
        assert not _should_skip_image("https://cdn.example.com/2026/03/protest.jpg")


# --- _convert_graphics_to_imgs tests ---


class TestConvertGraphicsToImgs:
    def test_converts_self_closing_graphic(self):
        html = '<graphic src="https://ichef.bbci.co.uk/news/480/photo.jpg" alt="A protest"/>'
        result = _convert_graphics_to_imgs(html)
        assert "<graphic" not in result
        assert '<img src="https://ichef.bbci.co.uk/news/480/photo.jpg" alt="A protest"/>' in result

    def test_converts_non_self_closing_graphic(self):
        html = '<graphic src="https://example.com/img.jpg" alt="desc">'
        result = _convert_graphics_to_imgs(html)
        assert "<graphic" not in result
        assert '<img src="https://example.com/img.jpg" alt="desc"/>' in result

    def test_preserves_existing_img_tags(self):
        html = '<img src="https://example.com/photo.jpg" alt="ok" />'
        result = _convert_graphics_to_imgs(html)
        assert result == html

    def test_handles_mixed_img_and_graphic(self):
        html = (
            '<img src="https://a.com/1.jpg" />'
            '<graphic src="https://b.com/2.jpg" alt="two"/>'
            '<img src="https://c.com/3.jpg" />'
        )
        result = _convert_graphics_to_imgs(html)
        assert "<graphic" not in result
        assert 'src="https://a.com/1.jpg"' in result
        assert 'src="https://b.com/2.jpg"' in result
        assert 'src="https://c.com/3.jpg"' in result

    def test_graphic_with_no_attributes(self):
        html = "<graphic/>"
        result = _convert_graphics_to_imgs(html)
        assert result == "<img/>"

    def test_multiple_graphics(self):
        html = (
            '<p>Text</p><graphic src="https://x.com/1.jpg" alt="one"/>'
            '<p>More</p><graphic src="https://x.com/2.jpg" alt="two"/>'
        )
        result = _convert_graphics_to_imgs(html)
        assert result.count("<img") == 2
        assert "<graphic" not in result

    def test_case_insensitive(self):
        html = '<GRAPHIC src="https://example.com/img.jpg" ALT="test"/>'
        result = _convert_graphics_to_imgs(html)
        assert "<GRAPHIC" not in result
        assert "<img" in result

    def test_no_graphics_returns_unchanged(self):
        html = "<p>No images here at all.</p>"
        result = _convert_graphics_to_imgs(html)
        assert result == html


# --- _process_article_images tests ---


class TestProcessArticleImages:
    def test_replaces_img_src_with_placeholder(self):
        # We can't download real images in tests, but we can test the
        # filtering and structural behavior. Test with HTML that has
        # no downloadable images — they get removed.
        html = '<p>Text</p><img src="https://ads.example.com/pixel.gif" /><p>More</p>'
        config = _make_config()
        new_html, images = _process_article_images(html, config)
        assert len(images) == 0
        assert "ads.example.com" not in new_html

    def test_removes_filtered_images(self):
        html = '<p>Hello</p><img src="https://example.com/logo.png" alt="Logo" />'
        config = _make_config()
        new_html, images = _process_article_images(html, config)
        assert len(images) == 0
        assert "<img" not in new_html

    def test_converts_graphic_tags_before_processing(self):
        """<graphic> tags from trafilatura are converted then processed like <img>."""
        # Use an ad-domain URL so the image gets filtered (no download needed)
        html = '<p>Text</p><graphic src="https://ads.example.com/pixel.gif" alt="ad"/><p>More</p>'
        config = _make_config()
        new_html, images = _process_article_images(html, config)
        assert "<graphic" not in new_html
        assert len(images) == 0

    def test_graphic_with_normal_url_gets_download_attempt(self):
        """<graphic> with a non-filtered URL triggers the download path."""
        from unittest.mock import patch

        html = '<graphic src="https://cdn.example.com/photos/hero.jpg" alt="Hero"/>'
        config = _make_config()

        # Mock _download_image to return None (simulates download failure)
        with patch("paper_boy.feeds._download_image", return_value=None):
            new_html, images = _process_article_images(html, config)

        # graphic tag should be gone (converted to img, then removed since download failed)
        assert "<graphic" not in new_html
        assert len(images) == 0


# --- EPUB with embedded images tests ---


def _make_sections_with_images():
    """Create test sections with pre-built ArticleImage objects."""
    img_data = _make_test_image(400, 300, "blue")
    return [
        Section(
            name="World",
            articles=[
                Article(
                    title="Article With Image",
                    url="https://example.com/1",
                    author="Alice",
                    html_content=(
                        "<p>Before image.</p>"
                        f'<figure><img src="{IMG_PLACEHOLDER_PREFIX}0__" '
                        'alt="Protest photo" />'
                        "<figcaption>Protesters in London</figcaption></figure>"
                        "<p>After image.</p>"
                    ),
                    images=[
                        ArticleImage(
                            data=img_data,
                            alt="Protest photo",
                            caption="Protesters in London",
                        ),
                    ],
                ),
                Article(
                    title="Article Without Image",
                    url="https://example.com/2",
                    html_content="<p>No images here.</p>",
                ),
            ],
        ),
    ]


def test_epub_contains_embedded_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        sections = _make_sections_with_images()
        build_epub(sections, _make_config(), date(2026, 3, 1), output)

        with zipfile.ZipFile(output) as z:
            names = z.namelist()
            image_files = [n for n in names if n.startswith("EPUB/images/article_")]
            assert len(image_files) == 1
            assert any("article_001_01.jpg" in n for n in image_files)


def test_epub_image_is_valid_jpeg():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        sections = _make_sections_with_images()
        build_epub(sections, _make_config(), date(2026, 3, 1), output)

        with zipfile.ZipFile(output) as z:
            image_files = [n for n in z.namelist() if "article_001_01.jpg" in n]
            assert image_files
            img_data = z.read(image_files[0])
            img = Image.open(BytesIO(img_data))
            assert img.format == "JPEG"


def test_epub_article_html_references_image():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        sections = _make_sections_with_images()
        build_epub(sections, _make_config(), date(2026, 3, 1), output)

        with zipfile.ZipFile(output) as z:
            article_files = [n for n in z.namelist() if "article_001.xhtml" in n]
            assert article_files
            html = z.read(article_files[0]).decode("utf-8")
            # Placeholder should be replaced with actual filename
            assert IMG_PLACEHOLDER_PREFIX not in html
            assert "images/article_001_01.jpg" in html
            assert "<figcaption>Protesters in London</figcaption>" in html


def test_epub_without_images_still_works():
    """Articles with no images should build normally."""
    sections = [
        Section(
            name="Tech",
            articles=[
                Article(
                    title="Plain Article",
                    url="https://example.com/1",
                    html_content="<p>Just text.</p>",
                ),
            ],
        ),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(sections, _make_config(), date(2026, 3, 1), output)
        assert output.exists()
        with zipfile.ZipFile(output) as z:
            image_files = [n for n in z.namelist() if n.startswith("EPUB/images/article_")]
            assert len(image_files) == 0


def test_epub_multiple_images_per_article():
    """Multiple images in a single article are all embedded."""
    img1 = _make_test_image(300, 200, "red")
    img2 = _make_test_image(500, 400, "green")

    sections = [
        Section(
            name="News",
            articles=[
                Article(
                    title="Multi-Image Article",
                    url="https://example.com/1",
                    html_content=(
                        f'<figure><img src="{IMG_PLACEHOLDER_PREFIX}0__" alt="First" /></figure>'
                        "<p>Some text between images.</p>"
                        f'<figure><img src="{IMG_PLACEHOLDER_PREFIX}1__" alt="Second" /></figure>'
                    ),
                    images=[
                        ArticleImage(data=img1, alt="First", caption=""),
                        ArticleImage(data=img2, alt="Second", caption=""),
                    ],
                ),
            ],
        ),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.epub"
        build_epub(sections, _make_config(), date(2026, 3, 1), output)

        with zipfile.ZipFile(output) as z:
            names = z.namelist()
            article_images = [n for n in names if n.startswith("EPUB/images/article_")]
            assert len(article_images) == 2
            assert any("article_001_01.jpg" in n for n in article_images)
            assert any("article_001_02.jpg" in n for n in article_images)
