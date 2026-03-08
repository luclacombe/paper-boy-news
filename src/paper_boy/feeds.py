"""RSS feed fetching and article text extraction."""

from __future__ import annotations

import json
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

from paper_boy.cache import ContentCache
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

# Regex to find TEI XML <graphic> tags output by trafilatura
# Matches both self-closing <graphic .../> and open <graphic ...> (no closing tag)
_GRAPHIC_TAG_RE = re.compile(r"<graphic\b([^>]*?)/?>", re.IGNORECASE)

# Regex to extract attributes from an <img> tag
_ATTR_RE = re.compile(r'([\w-]+)\s*=\s*["\']([^"\']*)["\']')

# Placeholder prefix used in HTML — replaced with real filenames in epub.py
IMG_PLACEHOLDER_PREFIX = "__paperboy_img_"

# --- Extraction fallback pipeline ---

# Minimum word count to consider an extraction successful (not truncated/paywalled)
MIN_ARTICLE_WORDS = 150

# Bot UA that publishers whitelist for SEO content discovery (same approach as Calibre)
_BOT_USER_AGENT = "Mozilla/5.0 (compatible; archive.org_bot; +https://archive.org)"

# URL path segments indicating non-article pages (video, podcasts, live streams)
_SKIP_URL_SEGMENTS = ("/video/", "/program/", "/podcasts/", "/live/")

# JSON-LD script tag extraction
_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

# Duplicate title detection — matches leading <h1> or <h2> in extracted HTML
_LEADING_HEADING_RE = re.compile(
    r"^\s*<(h[12])\b[^>]*>(.*?)</\1>\s*",
    re.IGNORECASE | re.DOTALL,
)

# HTML normalization patterns
_EMPTY_TAG_RE = re.compile(r"<(p|div|span)\b[^>]*>\s*</\1>", re.IGNORECASE)
_INLINE_STYLE_RE = re.compile(r'\s+style="[^"]*"', re.IGNORECASE)
_CAPTION_ARTIFACT_RE = re.compile(
    r"(hide\s+caption|toggle\s+caption|enlarge\s+this\s+image)",
    re.IGNORECASE,
)


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


def fetch_feeds(config: Config, cache: ContentCache | None = None) -> list[Section]:
    """Fetch all configured feeds and extract article content."""
    sections = []
    for feed_cfg in config.feeds:
        section = _fetch_single_feed(feed_cfg, config, cache=cache)
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


def _fetch_single_feed(
    feed_cfg: FeedConfig, config: Config, cache: ContentCache | None = None
) -> Section:
    """Fetch a single RSS feed and extract articles."""
    section = Section(name=feed_cfg.name)

    if not is_safe_url(feed_cfg.url):
        logger.warning("Blocked unsafe feed URL: %s", feed_cfg.url)
        return section

    # Check cache for parsed feed entries
    cached_entries = cache.get_feed(feed_cfg.url) if cache else None
    if cached_entries is not None:
        entries = cached_entries[: config.newspaper.max_articles_per_feed]
    else:
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

        # Cache the full entries list so users with higher limits still benefit
        if cache:
            cache.set_feed(feed_cfg.url, feed.entries)

        entries = feed.entries[: config.newspaper.max_articles_per_feed]

    for entry in entries:
        article = _extract_article(entry, config, cache=cache)
        if article:
            section.articles.append(article)

    return section


def _extract_article(
    entry, config: Config, cache: ContentCache | None = None
) -> Article | None:
    """Extract full article content from a feed entry."""
    url = entry.get("link", "")
    title = entry.get("title", "Untitled")

    if not url or not is_safe_url(url):
        return None

    # Skip non-article pages (video, podcasts, live streams)
    if any(seg in url for seg in _SKIP_URL_SEGMENTS):
        logger.debug("Skipping non-article URL: %s", url)
        return None

    include_images = config.newspaper.include_images

    # Check cache for previously extracted article HTML
    if cache:
        found, cached_html = cache.get_article(url, include_images)
        if found:
            html_content = cached_html
        else:
            html_content = _extract_article_content(url, include_images)
            cache.set_article(url, include_images, html_content)
    else:
        html_content = _extract_article_content(url, include_images)

    # Fall back to RSS feed content if extraction fails
    if not html_content:
        html_content = _get_feed_content(entry)

    if not html_content:
        logger.debug("Skipping article with no content: %s", title)
        return None

    # Strip duplicate title heading from extracted content
    # (epub.py adds its own <h1> from Article.title)
    html_content = _strip_duplicate_title(html_content, title)

    # Process images: download, optimize, rewrite HTML
    images: list[ArticleImage] = []
    if include_images and html_content:
        html_content, images = _process_article_images(html_content, config, cache=cache)

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


def _count_words(html: str) -> int:
    """Count words in HTML by stripping tags."""
    text = re.sub(r"<[^>]+>", " ", html)
    return len(text.split())


def _extract_article_content(url: str, include_images: bool) -> str | None:
    """Multi-strategy article extraction with fallback for paywalled content.

    Strategy chain:
    1. Standard trafilatura (default UA)
    2. Re-fetch with bot UA → trafilatura
    3. JSON-LD structured data from bot-fetched page
    Returns the first result with >= MIN_ARTICLE_WORDS, or the best short
    result, or None.
    """
    # Strategy 1: Standard trafilatura extraction
    result = _trafilatura_extract(url, include_images)
    if result and _count_words(result) >= MIN_ARTICLE_WORDS:
        return _normalize_html(result)

    # Strategy 2: Re-fetch with bot UA
    bot_page = _fetch_page(url, _BOT_USER_AGENT)
    if bot_page:
        bot_result = _trafilatura_extract_from_html(bot_page, include_images)
        if bot_result and _count_words(bot_result) >= MIN_ARTICLE_WORDS:
            logger.debug("Extraction strategy 'bot_ua' succeeded for %s", url)
            return _normalize_html(bot_result)

        # Strategy 3: JSON-LD from the bot-fetched page
        json_ld_result = _extract_from_json_ld(bot_page)
        if json_ld_result and _count_words(json_ld_result) >= MIN_ARTICLE_WORDS:
            logger.debug("Extraction strategy 'json_ld' succeeded for %s", url)
            return _normalize_html(json_ld_result)

    # Return best short result we have, normalized
    if result:
        return _normalize_html(result)
    return None


def _trafilatura_extract(url: str, include_images: bool) -> str | None:
    """Download and extract article content via trafilatura (default UA)."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            return trafilatura.extract(
                downloaded,
                include_images=include_images,
                include_links=False,
                output_format="html",
            )
        return None
    except Exception:
        logger.warning("Failed to extract article: %s", url, exc_info=True)
        return None


def _trafilatura_extract_from_html(
    html_source: str, include_images: bool
) -> str | None:
    """Extract article content from pre-downloaded HTML via trafilatura."""
    try:
        return trafilatura.extract(
            html_source,
            include_images=include_images,
            include_links=False,
            output_format="html",
        )
    except Exception:
        logger.debug("trafilatura extraction from HTML failed", exc_info=True)
        return None


def _fetch_page(url: str, user_agent: str) -> str | None:
    """Download a web page and return HTML source."""
    if not is_safe_url(url):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return data.decode(charset, errors="replace")
    except Exception:
        logger.debug("Failed to fetch page: %s", url, exc_info=True)
        return None


def _extract_from_json_ld(html_source: str) -> str | None:
    """Extract article body from JSON-LD structured data.

    Many publishers embed full article text in <script type="application/ld+json">
    for SEO. This is the same data Google reads — publicly served structured data.
    """
    for match in _JSON_LD_RE.finditer(html_source):
        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue

        # Handle both single objects and @graph arrays
        items: list[dict] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "@graph" in data:
                graph = data["@graph"]
                items = graph if isinstance(graph, list) else []
            else:
                items = [data]

        for item in items:
            if not isinstance(item, dict):
                continue
            body = item.get("articleBody") or item.get("text")
            if not body or len(body) < 100:
                continue
            # Convert plain text to paragraph-wrapped HTML
            paragraphs = body.split("\n\n")
            if len(paragraphs) <= 1:
                paragraphs = body.split("\n")
            html_parts = [f"<p>{p.strip()}</p>" for p in paragraphs if p.strip()]
            if html_parts:
                return "\n".join(html_parts)

    return None


def _normalize_html(html: str) -> str:
    """Normalize extracted HTML for consistent EPUB output.

    Applied to ALL extraction paths (trafilatura, bot UA, JSON-LD) for
    consistent output.
    """
    # Remove empty tags
    html = _EMPTY_TAG_RE.sub("", html)
    # Strip inline styles
    html = _INLINE_STYLE_RE.sub("", html)
    # Remove NPR caption artifacts
    html = _CAPTION_ARTIFACT_RE.sub("", html)
    return html.strip()


def _strip_duplicate_title(html: str, title: str) -> str:
    """Remove leading <h1>/<h2> from extracted HTML if it matches the article title.

    trafilatura often includes the article title as an <h1> in the extracted
    HTML, but epub.py already adds its own <h1> from the Article.title field.
    This prevents the title from appearing twice.

    Uses fuzzy matching: lowercased, stripped of punctuation, and checks
    containment in both directions to handle minor editorial differences.
    """
    match = _LEADING_HEADING_RE.match(html)
    if not match:
        return html

    heading_text = re.sub(r"<[^>]+>", "", match.group(2)).strip()

    def _normalize_for_compare(s: str) -> str:
        return re.sub(r"[^\w\s]", "", s).lower().strip()

    norm_heading = _normalize_for_compare(heading_text)
    norm_title = _normalize_for_compare(title)

    if not norm_heading or not norm_title:
        return html

    # Exact match or containment in either direction
    if norm_heading == norm_title or norm_heading in norm_title or norm_title in norm_heading:
        return html[match.end():]

    return html


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


def _convert_graphics_to_imgs(html: str) -> str:
    """Convert TEI XML <graphic> tags to standard HTML <img> tags.

    trafilatura with output_format="html" and include_images=True emits
    <graphic src="..." alt="..."/> instead of <img> tags. These are invisible
    to e-readers, so we normalise them before the image pipeline runs.
    """
    return _GRAPHIC_TAG_RE.sub(r"<img\1/>", html)


def _process_article_images(
    html: str,
    config: Config,
    cache: ContentCache | None = None,
) -> tuple[str, list[ArticleImage]]:
    """Download images from article HTML, optimize them, replace src with placeholders.

    Returns (rewritten_html, list_of_ArticleImage).
    Placeholder src values like __paperboy_img_0__ are replaced with real
    EPUB filenames later in epub.py.
    """
    # Convert TEI XML <graphic> tags to <img> before processing
    html = _convert_graphics_to_imgs(html)

    images: list[ArticleImage] = []
    counter = [0]  # mutable counter for the closure

    def _replace_img(match: re.Match) -> str:
        tag = match.group(0)
        attrs = dict(_ATTR_RE.findall(tag))

        # Prefer data-src (lazy-loaded images) over src
        src = attrs.get("data-src") or attrs.get("src", "")
        if not src or _should_skip_image(src):
            return ""

        image_data = _download_image(src, cache=cache)
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


def _download_image(
    url: str, timeout: int = 10, cache: ContentCache | None = None
) -> bytes | None:
    """Download an image from a URL. Returns bytes or None on failure."""
    if not is_safe_url(url):
        return None

    # Check cache for previously downloaded image
    if cache:
        found, cached_data = cache.get_image(url)
        if found:
            return cached_data

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PaperBoy/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if cache:
            cache.set_image(url, data)
        return data
    except Exception:
        logger.debug("Failed to download image: %s", url, exc_info=True)
        if cache:
            cache.set_image(url, None)
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
