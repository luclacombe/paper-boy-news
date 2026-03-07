"""RSS feed fetching and article text extraction."""

from __future__ import annotations

import logging
import re
import signal
import urllib.request
from dataclasses import dataclass, field
from io import BytesIO
from urllib.parse import urlparse

import feedparser
import trafilatura
from PIL import Image

from paper_boy.config import Config, FeedConfig
from paper_boy.url_validation import is_safe_url

logger = logging.getLogger(__name__)

# --- Image filtering ---

_AD_DOMAINS = frozenset(
    {
        "doubleclick.net",
        "googlesyndication.com",
        "facebook.com",
        "pixel.",
        "analytics.",
        "tracking.",
        "ads.",
        "ad.",
        "beacon.",
    }
)

_SKIP_PATTERNS = re.compile(
    r"(logo|icon|avatar|sprite|banner|ad[-_]|tracking|badge|button|widget|social)",
    re.IGNORECASE,
)

# Generic alt text that shouldn't become captions
_GENERIC_ALT = frozenset(
    {"image", "photo", "img", "picture", "thumbnail", "thumb", ""}
)

# Regex to find <img> tags in HTML
_IMG_TAG_RE = re.compile(r"<img\b[^>]*?/?>", re.IGNORECASE)

# Regex to extract attributes from an <img> tag
_ATTR_RE = re.compile(r'([\w-]+)\s*=\s*["\']([^"\']*)["\']')

# Placeholder prefix used in HTML — replaced with real filenames in epub.py
IMG_PLACEHOLDER_PREFIX = "__paperboy_img_"


# --- Dataclasses ---


@dataclass
class ArticleImage:
    """An optimized image ready for EPUB embedding."""

    data: bytes
    alt: str = ""
    caption: str = ""


@dataclass
class Article:
    title: str
    url: str
    author: str | None = None
    date: str | None = None
    html_content: str = ""
    images: list[ArticleImage] = field(default_factory=list)


@dataclass
class Section:
    name: str
    articles: list[Article] = field(default_factory=list)


# --- Public API ---


def fetch_feeds(config: Config) -> list[Section]:
    """Fetch all configured feeds and extract article content."""
    sections = []
    for feed_cfg in config.feeds:
        section = _fetch_single_feed(feed_cfg, config)
        if section.articles:
            sections.append(section)
            logger.info(
                "Fetched %d articles from %s", len(section.articles), feed_cfg.name
            )
        else:
            logger.warning("No articles extracted from %s", feed_cfg.name)
    return sections


# --- Feed fetching ---


_FEED_FETCH_TIMEOUT = 30  # seconds


def _fetch_single_feed(feed_cfg: FeedConfig, config: Config) -> Section:
    """Fetch a single RSS feed and extract articles."""
    section = Section(name=feed_cfg.name)

    if not is_safe_url(feed_cfg.url):
        logger.warning("Blocked unsafe feed URL: %s", feed_cfg.url)
        return section

    def _timeout_handler(signum, frame):
        raise TimeoutError(f"Feed fetch timed out after {_FEED_FETCH_TIMEOUT}s")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(_FEED_FETCH_TIMEOUT)
    try:
        feed = feedparser.parse(feed_cfg.url)
    except TimeoutError:
        logger.warning("Feed fetch timed out: %s", feed_cfg.name)
        return section
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    if feed.bozo and not feed.entries:
        logger.error("Failed to parse feed %s: %s", feed_cfg.name, feed.bozo_exception)
        return section

    entries = feed.entries[: config.newspaper.max_articles_per_feed]

    for entry in entries:
        article = _extract_article(entry, config)
        if article:
            section.articles.append(article)

    return section


def _extract_article(entry, config: Config) -> Article | None:
    """Extract full article content from a feed entry."""
    url = entry.get("link", "")
    title = entry.get("title", "Untitled")

    if not url or not is_safe_url(url):
        return None

    include_images = config.newspaper.include_images

    # Try to extract full article text from the URL
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            html_content = trafilatura.extract(
                downloaded,
                include_images=include_images,
                include_links=False,
                output_format="html",
            )
        else:
            html_content = None
    except Exception:
        logger.warning("Failed to extract article: %s", url, exc_info=True)
        html_content = None

    # Fall back to RSS feed content if extraction fails
    if not html_content:
        html_content = _get_feed_content(entry)

    if not html_content:
        logger.debug("Skipping article with no content: %s", title)
        return None

    # Process images: download, optimize, rewrite HTML
    images: list[ArticleImage] = []
    if include_images and html_content:
        html_content, images = _process_article_images(html_content, config)

    # Extract author
    author = entry.get("author")
    if not author and entry.get("authors"):
        author = entry["authors"][0].get("name")

    # Extract date
    date = entry.get("published") or entry.get("updated")

    return Article(
        title=title,
        url=url,
        author=author,
        date=date,
        html_content=html_content,
        images=images,
    )


def _get_feed_content(entry) -> str | None:
    """Extract content from the RSS feed entry itself (fallback)."""
    # Try content field first (often has full HTML)
    if entry.get("content"):
        for content in entry["content"]:
            if content.get("value"):
                return content["value"]

    # Try summary/description
    summary = entry.get("summary", "")
    if summary and len(summary) > 100:
        return summary

    return None


# --- Image processing pipeline ---


def _process_article_images(
    html: str,
    config: Config,
) -> tuple[str, list[ArticleImage]]:
    """Download images from article HTML, optimize them, replace src with placeholders.

    Returns (rewritten_html, list_of_ArticleImage).
    Placeholder src values like __paperboy_img_0__ are replaced with real
    EPUB filenames later in epub.py.
    """
    images: list[ArticleImage] = []
    counter = [0]  # mutable counter for the closure

    def _replace_img(match: re.Match) -> str:
        tag = match.group(0)
        attrs = dict(_ATTR_RE.findall(tag))

        # Prefer data-src (lazy-loaded images) over src
        src = attrs.get("data-src") or attrs.get("src", "")
        if not src or _should_skip_image(src):
            return ""

        image_data = _download_image(src)
        if image_data is None:
            return ""

        optimized = optimize_image(
            image_data,
            max_width=config.newspaper.image_max_width,
            max_height=config.newspaper.image_max_height,
            quality=config.newspaper.image_quality,
            min_dimension=config.newspaper.image_min_dimension,
        )
        if optimized is None:
            return ""

        idx = counter[0]
        counter[0] += 1

        alt = attrs.get("alt", "").strip()
        title = attrs.get("title", "").strip()
        caption = title or (alt if alt.lower() not in _GENERIC_ALT else "")

        images.append(ArticleImage(data=optimized, alt=alt, caption=caption))

        placeholder = f"{IMG_PLACEHOLDER_PREFIX}{idx}__"
        alt_attr = f' alt="{alt}"' if alt else ""

        # Build the replacement HTML
        img_tag = f'<img src="{placeholder}"{alt_attr} />'
        if caption:
            return (
                f"<figure>{img_tag}"
                f"<figcaption>{caption}</figcaption>"
                f"</figure>"
            )
        return f"<figure>{img_tag}</figure>"

    # Replace all <img> tags. Remove empty <figure> wrappers if the image
    # was filtered out (returns "").
    new_html = _IMG_TAG_RE.sub(_replace_img, html)

    # Clean up any existing <figure> that now wraps nothing (image was removed)
    new_html = re.sub(
        r"<figure>\s*</figure>", "", new_html, flags=re.IGNORECASE
    )

    return new_html, images


def _should_skip_image(url: str) -> bool:
    """Filter out ads, tracking pixels, icons, and logos by URL."""
    parsed = urlparse(url)

    for ad_domain in _AD_DOMAINS:
        if ad_domain in parsed.netloc:
            return True

    if _SKIP_PATTERNS.search(parsed.path):
        return True

    if any(
        seg in parsed.path
        for seg in ("/ads/", "/tracking/", "/widgets/", "/social/")
    ):
        return True

    return False


def _download_image(url: str, timeout: int = 10) -> bytes | None:
    """Download an image from a URL. Returns bytes or None on failure."""
    if not is_safe_url(url):
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PaperBoy/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        logger.debug("Failed to download image: %s", url, exc_info=True)
        return None


def optimize_image(
    image_data: bytes,
    max_width: int = 800,
    max_height: int = 1200,
    quality: int = 80,
    min_dimension: int = 100,
) -> bytes | None:
    """Optimize an image for e-reader display.

    Returns optimized JPEG bytes, or None if the image should be skipped
    (e.g. too small — likely a tracking pixel or icon).
    """
    try:
        img = Image.open(BytesIO(image_data))
    except Exception:
        return None

    # Filter out tiny images (tracking pixels, icons, social buttons)
    if img.width < min_dimension or img.height < min_dimension:
        return None

    # Convert to RGB if necessary (JPEG doesn't support alpha)
    if img.mode in ("RGBA", "P", "LA", "PA"):
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize if too wide
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Resize if too tall (prevents tall infographics from dominating pages)
    if img.height > max_height:
        ratio = max_height / img.height
        new_size = (int(img.width * ratio), max_height)
        img = img.resize(new_size, Image.LANCZOS)

    # Save as optimized JPEG
    output = BytesIO()
    img.save(output, format="JPEG", quality=quality, optimize=True)
    return output.getvalue()
