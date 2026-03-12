"""RSS feed fetching and article text extraction."""

from __future__ import annotations

import gzip
import html as _html_mod
import http.client
import json
import logging
import random
import re
import signal
import ssl
import http.cookiejar
import urllib.request

# Some servers (e.g. Business of Fashion) send >100 response headers,
# exceeding Python's default _MAXHEADERS=100 and crashing http.client.
http.client._MAXHEADERS = 200
from dataclasses import dataclass, field
from io import BytesIO
from urllib.parse import urlparse

import feedparser
import trafilatura
from PIL import Image

from paper_boy.cache import ContentCache
from paper_boy.config import Config, FeedConfig
from paper_boy.filters import (
    check_quality,
    detect_paywall,
    strip_bbc_related,
    strip_junk,
    strip_sciencedaily_metadata,
    strip_section_junk,
    strip_trailing_junk,
)
from paper_boy.url_validation import is_safe_url

logger = logging.getLogger(__name__)

# --- Performance safeguards ---

# Abort a feed after this many consecutive extraction failures
_MAX_CONSECUTIVE_FAILURES = 3

# Domain-level extraction failure tracking.
# After _DOMAIN_FAILURE_THRESHOLD failures on strategy 1 (trafilatura),
# skip strategies 1.5–4 for all subsequent articles from that domain.
_DOMAIN_FAILURE_THRESHOLD = 2
_domain_failures: dict[str, int] = {}


def _reset_domain_failures() -> None:
    """Clear domain failure tracking. Called at the start of each build."""
    _domain_failures.clear()


def _record_domain_failure(url: str) -> None:
    """Record a strategy-1 extraction failure for a domain."""
    domain = urlparse(url).netloc
    if domain:
        _domain_failures[domain] = _domain_failures.get(domain, 0) + 1


def _domain_is_blocked(url: str) -> bool:
    """Check if a domain has exceeded the failure threshold."""
    domain = urlparse(url).netloc
    return _domain_failures.get(domain, 0) >= _DOMAIN_FAILURE_THRESHOLD


# Auth/login URL patterns — detected after redirect to abort early
_AUTH_URL_PATTERNS = ("/login", "/authorize", "/signin", "/auth/")

# --- Image filtering ---

# Full domains checked with substring match
_AD_DOMAINS_FULL = frozenset(
    {
        "doubleclick.net",
        "googlesyndication.com",
        "facebook.com",
    }
)
# Subdomain prefixes — only match when they START the netloc (e.g. "pixel.example.com")
# NOT as substrings (avoids "petapixel.com" matching "pixel.")
_AD_SUBDOMAIN_PREFIXES = (
    "pixel.",
    "analytics.",
    "tracking.",
    "ads.",
    "ad.",
    "beacon.",
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
_BOT_USER_AGENT = "Mozilla/5.0 (Java) outbrain"

# Browser-like UA for bypassing interstitials (e.g. Nature)
_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Googlebot UA for sites that only whitelist Google's crawler (e.g. Smithsonian)
_GOOGLEBOT_USER_AGENT = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

# Domains that require Googlebot UA (all other UAs get 403)
_GOOGLEBOT_DOMAINS = {"smithsonianmag.com"}

# Bloomberg mobile API (unauthenticated CDN, returns full article JSON/HTML)
# Technique from Calibre's bloomberg.recipe by unkn0wn
_BLOOMBERG_CDN = "https://cdn-mobapi.bloomberg.com"
_BLOOMBERG_BW_STORIES = f"{_BLOOMBERG_CDN}/wssmobile/v1/bw/news/stories/"
_BLOOMBERG_NAV = f"{_BLOOMBERG_CDN}/wssmobile/v1/navigation/bloomberg_app/search-v2"
_BLOOMBERG_BW_LIST = f"{_BLOOMBERG_CDN}/wssmobile/v1/bw/news/list?limit=1"

# Reuters mobile app API (returns structured JSON with full article content)
# Technique from Calibre's reuters.recipe by unkn0wn
_REUTERS_BASE = "https://www.reuters.com"
_REUTERS_API_UA = (
    "ReutersNews/7.11.0.1742843009 Mozilla/5.0 (Linux; Android 14) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"
)
_REUTERS_GEO_COOKIE = 'reuters-geo={"country":"-"; "region":"-"}='

# Archive.today mirror TLDs for soft-paywalled content
# Technique from Calibre's project_syndicate.recipe by Kovid Goyal
_ARCHIVE_TLDS = ("fo", "is", "li", "md", "ph", "vn")

# LibreSSL (macOS system Python) cannot complete TLS handshakes with
# archive.today — each attempt burns ~12s waiting for the 15s timeout.
# With 6 TLDs per article, that's ~72s of pure waste per failed article.
# Detect LibreSSL at import time and skip archive.today strategy entirely.
_HAS_MODERN_SSL = "LibreSSL" not in ssl.OPENSSL_VERSION

# Scientific American base URL
# Uses __DATA__ JSON on issue page for article discovery (no RSS feed available).
# Technique from Calibre's scientific_american.recipe by Kovid Goyal.
_SCIAM_BASE = "https://www.scientificamerican.com"

# Washington Post: Googlebot UA + Google referrer headers to bypass paywall.
# Content extracted from __NEXT_DATA__ JSON (Next.js server-rendered data).
# Technique from Calibre's wash_post.recipe by unkn0wn.
_WAPO_HEADERS = {
    "Referer": "https://www.google.com/",
    "X-Forwarded-For": "66.249.66.1",
}

# Pagination link detection (e.g. Ars Technica /2/, /3/)
_PAGINATION_LINK_RE = re.compile(r'href="([^"]*?/(\d+)/)"')

# URL path segments indicating non-article pages (video, podcasts, live streams)
_SKIP_URL_SEGMENTS = ("/video/", "/program/", "/podcasts/", "/live/")

# Title prefixes indicating premium/subscriber-only content.
# Entries with these prefixes are skipped before extraction (saves time and
# avoids triggering the consecutive failure abort on mixed free/premium feeds).
_PREMIUM_TITLE_PREFIXES = ("STAT+:",)


def _is_premium_title(title: str) -> bool:
    """Check if a title indicates premium/subscriber-only content."""
    return any(title.startswith(prefix) for prefix in _PREMIUM_TITLE_PREFIXES)

# Stock photo / internal alt text patterns (should be cleared to "")
_STOCK_ALT_RE = re.compile(r"^[A-Z]{2,}\d*_")
_FILENAME_ALT_RE = re.compile(r"^[\w_-]+\.\w{2,4}$")

# JSON-LD script tag extraction
_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

# Duplicate title detection — matches ALL <h1>/<h2> tags in extracted HTML
_ALL_HEADINGS_RE = re.compile(
    r"<(h[12])\b[^>]*>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL,
)

# HTML normalization patterns
_HTML_BODY_WRAPPER_RE = re.compile(r"</?(?:html|body)\b[^>]*>", re.IGNORECASE)
_EMPTY_TAG_RE = re.compile(r"<(p|div|span)\b[^>]*>\s*</\1>", re.IGNORECASE)
_INLINE_STYLE_RE = re.compile(r'\s+style="[^"]*"', re.IGNORECASE)
_CAPTION_ARTIFACT_RE = re.compile(
    r"(hide\s+caption|toggle\s+caption|enlarge\s+this\s+image)",
    re.IGNORECASE,
)

# Zero-width Unicode characters (Reuters, Al Jazeera, DW, The Verge)
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")

# TEI table artifacts from trafilatura (row → tr, cell → td)
_TEI_ROW_OPEN_RE = re.compile(r"<row\b([^>]*)>", re.IGNORECASE)
_TEI_ROW_CLOSE_RE = re.compile(r"</row>", re.IGNORECASE)
_TEI_CELL_OPEN_RE = re.compile(r"<cell\b([^>]*)>", re.IGNORECASE)
_TEI_CELL_CLOSE_RE = re.compile(r"</cell>", re.IGNORECASE)

# Nested <figure><figure> from Reuters mobile API
_NESTED_FIGURE_RE = re.compile(
    r"<figure\b[^>]*>\s*<figure\b[^>]*>(.*?)</figure>(.*?)</figure>",
    re.IGNORECASE | re.DOTALL,
)

# Self-closing empty tags: <p/>, <div/>, etc.
_SELF_CLOSING_BLOCK_RE = re.compile(r"<(p|div|span)\s*/>", re.IGNORECASE)

# CMS auto-generated alt-text figcaptions ("Image may contain...")
_CMS_ALT_FIGCAPTION_RE = re.compile(
    r"<figcaption[^>]*>\s*Image may contain\b[^<]*</figcaption>",
    re.IGNORECASE,
)

# Declarative normalization rules: (compiled_pattern, replacement)
# Applied sequentially — order matters (e.g. body wrapper must be first).
_NORMALIZE_RULES: list[tuple[re.Pattern, str]] = [
    (_HTML_BODY_WRAPPER_RE, ""),        # Strip <html>/<body> wrappers (must be first)
    (_ZERO_WIDTH_RE, ""),               # Strip zero-width Unicode chars
    (_SELF_CLOSING_BLOCK_RE, ""),       # Remove self-closing <p/>, <div/>, <span/>
    (_EMPTY_TAG_RE, ""),                # Remove empty tags
    (_INLINE_STYLE_RE, ""),             # Strip inline styles
    (_CAPTION_ARTIFACT_RE, ""),         # Remove NPR caption artifacts
    (_CMS_ALT_FIGCAPTION_RE, ""),      # Remove "Image may contain" figcaptions
    (_TEI_ROW_OPEN_RE, r"<tr\1>"),     # Convert TEI <row> → <tr>
    (_TEI_ROW_CLOSE_RE, "</tr>"),       # Convert </row> → </tr>
    (_TEI_CELL_OPEN_RE, r"<td\1>"),    # Convert TEI <cell> → <td>
    (_TEI_CELL_CLOSE_RE, "</td>"),      # Convert </cell> → </td>
    (_NESTED_FIGURE_RE, r"<figure>\1\2</figure>"),  # Flatten nested figures
]


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
    category: str = ""
    articles: list[Article] = field(default_factory=list)


# --- Public API ---


def fetch_feeds(config: Config, cache: ContentCache | None = None) -> list[Section]:
    """Fetch all configured feeds and extract article content."""
    _reset_domain_failures()
    sections = []
    for feed_cfg in config.feeds:
        try:
            section = _fetch_single_feed(feed_cfg, config, cache=cache)
        except Exception:
            logger.exception("Unexpected error fetching %s — skipping", feed_cfg.name)
            continue
        if section.articles:
            sections.append(section)
            logger.info(
                "Fetched %d articles from %s", len(section.articles), feed_cfg.name
            )
        else:
            logger.warning("No articles extracted from %s", feed_cfg.name)

    budget = config.newspaper.total_article_budget
    if budget > 0:
        sections = apply_article_budget(sections, budget)

    return sections


def apply_article_budget(sections: list[Section], budget: int) -> list[Section]:
    """Trim sections to fit within a total article budget.

    Guarantees at least 1 article per source (up to the budget).
    Distributes remaining budget round-robin across sources in order.
    """
    if not sections:
        return sections

    total = sum(len(s.articles) for s in sections)
    if total <= budget:
        return sections

    # More sources than budget — keep 1 article from the first `budget` sources
    if len(sections) >= budget:
        for section in sections[:budget]:
            section.articles = section.articles[:1]
        return sections[:budget]

    # Phase 1: allocate 1 article per source
    allocations = [1] * len(sections)
    remaining = budget - len(sections)

    # Phase 2: distribute remaining budget round-robin
    changed = True
    while remaining > 0 and changed:
        changed = False
        for i in range(len(sections)):
            if remaining <= 0:
                break
            if allocations[i] < len(sections[i].articles):
                allocations[i] += 1
                remaining -= 1
                changed = True

    # Apply allocations
    for i, section in enumerate(sections):
        section.articles = section.articles[: allocations[i]]

    return sections


# --- Feed fetching ---


_FEED_FETCH_TIMEOUT = 30  # seconds
_FETCH_CAP_PER_FEED = 20  # safety net — actual trimming done by apply_article_budget()


def _fetch_single_feed(
    feed_cfg: FeedConfig, config: Config, cache: ContentCache | None = None
) -> Section:
    """Fetch a single RSS feed and extract articles."""
    # Bloomberg and Reuters use mobile APIs instead of RSS
    if "bloomberg.com" in urlparse(feed_cfg.url).netloc:
        return _fetch_bloomberg_feed(feed_cfg, config, cache=cache)
    if "reuters.com" in urlparse(feed_cfg.url).netloc:
        return _fetch_reuters_feed(feed_cfg, config, cache=cache)
    if "scientificamerican.com" in urlparse(feed_cfg.url).netloc:
        return _fetch_sciam_feed(feed_cfg, config, cache=cache)

    section = Section(name=feed_cfg.name, category=feed_cfg.category)

    if not is_safe_url(feed_cfg.url):
        logger.warning("Blocked unsafe feed URL: %s", feed_cfg.url)
        return section

    # Check cache for parsed feed entries
    cached_entries = cache.get_feed(feed_cfg.url) if cache else None
    if cached_entries is not None:
        entries = cached_entries[: _FETCH_CAP_PER_FEED]
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

        entries = feed.entries[: _FETCH_CAP_PER_FEED]

    consecutive_failures = 0
    for entry in entries:
        # Skip entries explicitly marked as premium/subscriber-only by title
        entry_title = entry.get("title", "")
        if _is_premium_title(entry_title):
            logger.debug("Skipping premium entry: %s", entry_title)
            continue
        article = _extract_article(entry, config, cache=cache)
        if article:
            section.articles.append(article)
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                logger.info(
                    "Aborting %s after %d consecutive extraction failures",
                    feed_cfg.name,
                    consecutive_failures,
                )
                break

    return section


def _extract_article(
    entry, config: Config, cache: ContentCache | None = None
) -> Article | None:
    """Extract full article content from a feed entry."""
    url = entry.get("link", "")
    title = entry.get("title", "Untitled")

    if not url or not is_safe_url(url):
        return None

    # Skip non-article pages (video, podcasts, live streams, PDFs, YouTube)
    if any(seg in url for seg in _SKIP_URL_SEGMENTS):
        logger.debug("Skipping non-article URL: %s", url)
        return None

    parsed_url = urlparse(url)
    if parsed_url.path.lower().endswith(".pdf"):
        logger.debug("Skipping PDF URL: %s", url)
        return None

    if parsed_url.netloc and (
        "youtube.com" in parsed_url.netloc or "youtu.be" in parsed_url.netloc
    ):
        logger.debug("Skipping YouTube URL: %s", url)
        return None

    # HN self-posts link to the comments page — use feed content directly
    if "news.ycombinator.com/item" in url:
        html_content = _get_feed_content(entry)
        if not html_content:
            logger.debug("Skipping HN self-post with no feed content: %s", title)
            return None
        author = entry.get("author")
        if not author and entry.get("authors"):
            author = entry["authors"][0].get("name")
        date_str = entry.get("published") or entry.get("updated")
        return Article(
            title=title, url=url, author=author, date=date_str,
            html_content=html_content, images=[],
        )

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

    # Fall back to RSS feed content if extraction fails or is too short.
    # Some sites (e.g. Modern Farmer) return minimal page content but have
    # full articles in their RSS feed (common with WordPress full-content feeds).
    if not html_content or _count_words(html_content) < MIN_ARTICLE_WORDS:
        rss_content = _get_feed_content(entry)
        if rss_content and _count_words(rss_content) >= MIN_ARTICLE_WORDS:
            html_content = rss_content

    if not html_content:
        logger.debug("Skipping article with no content: %s", title)
        return None

    # Strip duplicate title heading from extracted content
    # (epub.py adds its own <h1> from Article.title)
    html_content = _strip_duplicate_title(html_content, title)

    # Downgrade any remaining <h1> to <h2> — epub.py adds its own <h1>
    html_content = _downgrade_body_headings(html_content)
    html_content = _dedup_consecutive_paragraphs(html_content)

    # Content filtering pipeline
    html_content = strip_junk(html_content)
    html_content = strip_sciencedaily_metadata(html_content)
    html_content = strip_bbc_related(html_content)
    html_content = strip_section_junk(html_content)
    html_content = strip_trailing_junk(html_content)
    if detect_paywall(html_content, url):
        logger.debug("Paywall detected, skipping: %s", title)
        return None
    if check_quality(html_content):
        logger.debug("Quality check failed, skipping: %s", title)
        return None

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


def _has_paywall_markers(html: str, url: str) -> bool:
    """Check if extracted HTML is paywall teaser text.

    Runs strip_junk first to remove promotional CTAs that might cause false
    positives (e.g. Nature's "Enjoying our latest content?" nag), then checks
    for actual paywall phrases. Used inside _extract_article_content() to
    prevent paywall teasers from short-circuiting the fallback chain.
    """
    cleaned = strip_junk(html)
    return detect_paywall(cleaned, url)


def _extract_article_content(url: str, include_images: bool) -> str | None:
    """Multi-strategy article extraction with fallback for paywalled content.

    Note: Bloomberg and Reuters are handled at the feed level (_fetch_bloomberg_feed,
    _fetch_reuters_feed) and never reach this function.

    Strategy chain:
    0. Domain-specific: Project Syndicate → archive.today (registration wall)
    1. Standard trafilatura (default UA)
    1.5. Re-fetch with browser UA (bypasses interstitials)
    2. Re-fetch with bot UA → trafilatura
    3. JSON-LD structured data from bot-fetched page
    4. Archive.today proxy (for soft-paywalled sites)
    Returns the first result with >= MIN_ARTICLE_WORDS, or the best short
    result, or None.
    """
    domain = urlparse(url).netloc

    # Strategy 0a: Washington Post — Googlebot UA + __NEXT_DATA__ JSON.
    # Standard extraction fails (trafilatura hangs, paywall blocks content).
    # Technique from Calibre's wash_post.recipe by unkn0wn.
    if "washingtonpost.com" in domain:
        if "/interactive/" in url:
            logger.debug("Skipping WaPo interactive page: %s", url)
            return None
        return _extract_wapo_article(url, include_images)

    # Strategy 0b: Googlebot-only domains — sites that 403 all UAs except
    # Googlebot (e.g. Smithsonian Magazine).
    if any(d in domain for d in _GOOGLEBOT_DOMAINS):
        page = _fetch_page(url, _GOOGLEBOT_USER_AGENT)
        if page:
            result = _trafilatura_extract_from_html(page, include_images)
            if result and _count_words(result) >= MIN_ARTICLE_WORDS:
                logger.debug("Googlebot UA succeeded for %s", url)
                return _normalize_html(result)
        return None

    # Strategy 0c: Project Syndicate — registration wall, go straight to
    # archive.today.  Technique from Calibre's project_syndicate.recipe by
    # unkn0wn.  Normal strategies only return the teaser paragraph (~50 words).
    if "project-syndicate.org" in domain:
        return _extract_via_archive(url, include_images)

    # Strategy 1: Standard trafilatura extraction
    result = _trafilatura_extract(url, include_images)
    if result and _count_words(result) >= MIN_ARTICLE_WORDS:
        if not _has_paywall_markers(result, url):
            # Paginated articles: fetch continuation pages (e.g. Ars Technica)
            if "arstechnica.com" in url:
                raw_page = _fetch_page(url, _BROWSER_USER_AGENT)
                if raw_page:
                    extra = _extract_paginated_content(url, raw_page, include_images)
                    if extra:
                        result = result + "\n" + extra
                        logger.debug("Appended paginated content for %s", url)
            return _normalize_html(result)
        logger.debug("Paywall detected in S1 result, trying fallbacks: %s", url)

    # Strategy 1.5: Re-fetch with browser UA (bypasses interstitials like
    # Nature's idp.nature.com cookie-setting redirect chain)
    browser_page = _fetch_page(url, _BROWSER_USER_AGENT)
    if browser_page:
        browser_result = _trafilatura_extract_from_html(browser_page, include_images)
        if browser_result and _count_words(browser_result) >= MIN_ARTICLE_WORDS:
            if not _has_paywall_markers(browser_result, url):
                logger.debug("Extraction strategy 'browser_ua' succeeded for %s", url)
                return _normalize_html(browser_result)
            logger.debug("Paywall detected in S1.5 result, trying fallbacks: %s", url)

    # Strategies 1 and 1.5 both failed — record domain failure for adaptive
    # skipping of the more expensive strategies 2-4.  Recording here (after
    # 1.5) instead of after strategy 1 alone prevents sites like Nature
    # (where trafilatura's own fetcher fails but our _fetch_page succeeds)
    # from being prematurely domain-blocked.
    #
    # Only record a domain failure when extraction truly failed (no content
    # or too few words).  If S1/S1.5 returned paywalled content, the site IS
    # accessible — it just needs a different UA (e.g. bot/outbrain for FT).
    # Recording paywall hits as domain failures would block S2, which is
    # exactly the strategy that works for paywalled sites.
    s1_was_paywall = result and _count_words(result) >= MIN_ARTICLE_WORDS
    if not s1_was_paywall:
        _record_domain_failure(url)

    # If this domain has failed repeatedly, skip the expensive fallback chain
    if _domain_is_blocked(url):
        logger.debug("Domain blocked after repeated failures, skipping fallbacks: %s", url)
        if result:
            return _normalize_html(result)
        return None

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

    # Strategy 4: Archive.today proxy (for soft-paywalled sites)
    archive_result = _extract_via_archive(url, include_images)
    if archive_result:
        logger.debug("Extraction strategy 'archive' succeeded for %s", url)
        return _normalize_html(archive_result)

    # Return best short result we have, normalized
    if result:
        return _normalize_html(result)
    return None


def _extract_wapo_article(url: str, include_images: bool) -> str | None:
    """Extract a Washington Post article via __NEXT_DATA__ JSON.

    Fetches the page with Googlebot UA + Google referrer headers, then parses
    the structured content from Next.js server-rendered data. This bypasses
    TWP's paywall because Google's crawler is whitelisted.
    Technique from Calibre's wash_post.recipe by unkn0wn.
    """
    page = _fetch_page(url, _GOOGLEBOT_USER_AGENT, _WAPO_HEADERS)
    if not page:
        return None

    m = re.search(
        r'<script\s+id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.DOTALL
    )
    if not m:
        logger.debug("No __NEXT_DATA__ in WaPo page: %s", url)
        return None

    try:
        data = json.loads(m.group(1))
        gc = data.get("props", {}).get("pageProps", {}).get("globalContent", {})
        if not gc:
            return None
    except (json.JSONDecodeError, KeyError):
        logger.debug("Failed to parse WaPo __NEXT_DATA__: %s", url)
        return None

    parts: list[str] = []
    for el in gc.get("content_elements", []):
        el_type = el.get("type", "")
        if el_type == "text":
            parts.append(f"<p>{el.get('content', '')}</p>")
        elif el_type == "header":
            level = el.get("level", 2)
            parts.append(f"<h{level}>{el.get('content', '')}</h{level}>")
        elif el_type == "list":
            items = "".join(
                f"<li>{li.get('content', '')}</li>"
                for li in el.get("items", [])
                if li.get("content", "")
            )
            if items:
                list_type = el.get("list_type", "unordered")
                tag = "ol" if list_type == "ordered" else "ul"
                parts.append(f"<{tag}>{items}</{tag}>")
        elif el_type == "image" and include_images:
            img_url = el.get("url", "")
            caption = el.get("credits_caption_display", "")
            if img_url:
                parts.append(
                    f'<figure><img src="{img_url}" alt=""/>'
                    f"<figcaption>{caption}</figcaption></figure>"
                )

    body = "\n".join(parts)
    if _count_words(body) < MIN_ARTICLE_WORDS:
        return None
    return _normalize_html(body)


def _fetch_bloomberg_api(url: str) -> dict | list | None:
    """Fetch a Bloomberg mobile API endpoint and return parsed JSON.

    The CDN API returns gzip-encoded responses; handles decompression.
    Technique from Calibre's bloomberg.recipe by unkn0wn.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Encoding": "gzip",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            return json.loads(data.decode("utf-8"))
    except Exception:
        logger.debug("Bloomberg API fetch failed: %s", url, exc_info=True)
        return None


def _resolve_bloomberg_section(section_name: str) -> str | None:
    """Resolve a section name to its Bloomberg API href via the navigation API.

    section_name is the URL path segment (e.g. 'technology', 'markets').
    Returns the full API path (e.g. '/wssmobile/v1/pages/business/phx-technology').
    """
    nav = _fetch_bloomberg_api(_BLOOMBERG_NAV)
    if not nav:
        return None
    for group in nav.get("searchNav", []):
        for item in group.get("items", []):
            if item.get("id") == section_name:
                return item.get("links", {}).get("self", {}).get("href")
    return None


def _fetch_bloomberg_feed(
    feed_cfg: FeedConfig, config: Config, cache: ContentCache | None = None
) -> Section:
    """Fetch articles from Bloomberg via the mobile app API.

    Bloomberg has no RSS feeds; the mobile CDN API returns section listings
    and full article HTML. Feed URL should be a bloomberg.com section URL
    (e.g. /technology/, /markets/) or /businessweek/ for the latest issue.
    Technique from Calibre's bloomberg.recipe by unkn0wn.
    """
    section = Section(name=feed_cfg.name, category=feed_cfg.category)

    parsed = urlparse(feed_cfg.url)
    path = parsed.path.strip("/")
    # e.g. "technology", "markets", "businessweek"
    sec_name = path.split("/")[-1] if path else ""

    if sec_name == "businessweek":
        stories = _fetch_bloomberg_bw_stories()
    else:
        stories = _fetch_bloomberg_section_stories(sec_name)

    if not stories:
        logger.warning("Bloomberg API returned no stories for %s", feed_cfg.name)
        return section

    include_images = config.newspaper.include_images
    seen_ids: set[str] = set()

    for story in stories[:_FETCH_CAP_PER_FEED]:
        story_id = story.get("internalID") or story.get("id", "")
        if not story_id or story_id in seen_ids:
            continue
        seen_ids.add(story_id)

        # Build a canonical URL for cache keying and display
        long_url = story.get("longURL", f"https://www.bloomberg.com/news/articles/{story_id}")

        # Check cache
        byline = story.get("byline")
        if cache:
            found, cached_html = cache.get_article(long_url, include_images)
            if found:
                html_content = cached_html
            else:
                html_content, api_byline = _extract_bloomberg_article(story_id)
                if not byline:
                    byline = api_byline
                cache.set_article(long_url, include_images, html_content)
        else:
            html_content, api_byline = _extract_bloomberg_article(story_id)
            if not byline:
                byline = api_byline

        if not html_content:
            continue

        # Normalize HTML
        html_content = _normalize_html(html_content)

        # Process images if requested
        images: list[ArticleImage] = []
        if include_images and html_content:
            html_content, images = _process_article_images(
                html_content, config, cache=cache
            )

        article = Article(
            title=story.get("title", "Untitled"),
            url=long_url,
            author=byline,
            date=None,  # published is a unix timestamp; set below
            html_content=html_content,
            images=images,
        )

        # Convert unix timestamp to RFC 2822 date string
        published = story.get("published")
        if published:
            from email.utils import formatdate
            try:
                article.date = formatdate(int(published), usegmt=True)
            except (ValueError, TypeError):
                pass

        section.articles.append(article)

    return section


def _fetch_bloomberg_section_stories(section_name: str) -> list[dict]:
    """Fetch story list from a Bloomberg section via the mobile API."""
    api_path = _resolve_bloomberg_section(section_name)
    if not api_path:
        logger.warning("Bloomberg section not found: %s", section_name)
        return []

    data = _fetch_bloomberg_api(f"{_BLOOMBERG_CDN}{api_path}")
    if not data:
        return []

    stories: list[dict] = []
    seen_ids: set[str] = set()
    for module in data.get("modules", []):
        for story in module.get("stories", []):
            sid = story.get("internalID", "")
            if story.get("type") in ("article", "interactive") and sid not in seen_ids:
                seen_ids.add(sid)
                stories.append(story)

    return stories


def _fetch_bloomberg_bw_stories() -> list[dict]:
    """Fetch story list from the latest Bloomberg Businessweek issue."""
    data = _fetch_bloomberg_api(_BLOOMBERG_BW_LIST)
    if not data:
        return []

    magazines = data.get("magazines", [])
    if not magazines:
        return []

    mag_id = magazines[0].get("id")
    if not mag_id:
        return []

    toc_url = f"{_BLOOMBERG_CDN}/wssmobile/v1/bw/news/week/{mag_id}"
    toc = _fetch_bloomberg_api(toc_url)
    if not toc:
        return []

    stories: list[dict] = []
    for module in toc.get("modules", []):
        for article in module.get("articles", []):
            # BW articles use "id" not "internalID"
            stories.append(article)

    return stories


def _extract_bloomberg_article(story_id: str) -> tuple[str | None, str | None]:
    """Extract full article HTML from Bloomberg's mobile API.

    Uses the /bw/news/stories/ endpoint which returns pre-rendered HTML.
    Returns (html, byline) tuple.
    Technique from Calibre's bloomberg.recipe by unkn0wn.
    """
    data = _fetch_bloomberg_api(f"{_BLOOMBERG_BW_STORIES}{story_id}")
    if not data:
        return None, None
    html = data.get("html", "")
    byline = data.get("byline")
    if not html or _count_words(html) < MIN_ARTICLE_WORDS:
        return None, byline
    return html, byline


def _fetch_reuters_api(path: str) -> dict | list | None:
    """Fetch a Reuters mobile API endpoint and return parsed JSON.

    Technique from Calibre's reuters.recipe by unkn0wn.
    """
    url = f"{_REUTERS_BASE}/mobile/v1{path}?outputType=json"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": _REUTERS_API_UA,
                "Cookie": _REUTERS_GEO_COOKIE,
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        logger.debug("Reuters API fetch failed: %s", url, exc_info=True)
        return None


def _fetch_reuters_feed(
    feed_cfg: FeedConfig, config: Config, cache: ContentCache | None = None
) -> Section:
    """Fetch articles from Reuters via the mobile app API.

    Reuters killed public RSS feeds; the mobile API returns structured JSON
    with full article content — no HTML extraction needed.
    Feed URL should be a reuters.com section URL (e.g. /world/, /business/).
    """
    section = Section(name=feed_cfg.name, category=feed_cfg.category)

    # Derive the section path from the feed URL
    # e.g. "https://www.reuters.com/world/" → "/world/"
    parsed = urlparse(feed_cfg.url)
    sec_path = parsed.path.rstrip("/") + "/"
    if not sec_path.startswith("/"):
        sec_path = "/" + sec_path

    data = _fetch_reuters_api(sec_path)
    if not data:
        logger.warning("Reuters API returned no data for %s", feed_cfg.name)
        return section

    # Extract stories from the section listing
    stories: list[dict] = []
    items = data if isinstance(data, list) else [data]
    for item in items:
        if isinstance(item, dict):
            for story in item.get("data", {}).get("stories", []):
                stories.append(story)

    seen_urls: set[str] = set()
    for story in stories[:_FETCH_CAP_PER_FEED]:
        story_url = story.get("url", "")
        if not story_url or story_url in seen_urls:
            continue
        seen_urls.add(story_url)

        full_url = _REUTERS_BASE + story_url

        # Check cache
        include_images = config.newspaper.include_images
        if cache:
            found, cached_html = cache.get_article(full_url, include_images)
            if found:
                html_content = cached_html
            else:
                html_content = _extract_reuters_article(story_url, include_images)
                cache.set_article(full_url, include_images, html_content)
        else:
            html_content = _extract_reuters_article(story_url, include_images)

        if not html_content:
            continue

        # Process images if requested
        images: list[ArticleImage] = []
        if include_images and html_content:
            html_content, images = _process_article_images(
                html_content, config, cache=cache
            )

        article = Article(
            title=story.get("title", "Untitled"),
            url=full_url,
            author=None,  # Set from article detail below if available
            date=story.get("display_time"),
            html_content=html_content,
            images=images,
        )
        section.articles.append(article)

    return section


def _extract_reuters_article(story_path: str, include_images: bool) -> str | None:
    """Extract a single Reuters article via the mobile API.

    Returns clean HTML built from the structured JSON content elements.
    """
    data = _fetch_reuters_api(story_path)
    if not data:
        return None

    items = data if isinstance(data, list) else [data]
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "article_detail":
            continue

        article = item.get("data", {}).get("article", {})
        parts: list[str] = []

        # Description as italic lead paragraph
        desc = article.get("description")
        if desc:
            parts.append(f"<p><em>{desc}</em></p>")

        # Authors
        authors = article.get("authors", [])
        if authors:
            bylines = ", ".join(a.get("byline", "") for a in authors if a.get("byline"))
            if bylines:
                parts.append(f"<p><small>By {bylines}</small></p>")

        # Lead image
        thumb = article.get("thumbnail")
        if include_images and thumb and thumb.get("type") == "image":
            resizer_url = thumb.get("resizer_url", "")
            if resizer_url:
                img_url = resizer_url.split("&")[0] + "&width=800"
                caption = thumb.get("caption", "")
                if caption:
                    parts.append(
                        f'<figure><img src="{img_url}" alt="" />'
                        f"<figcaption>{caption}</figcaption></figure>"
                    )
                else:
                    parts.append(f'<figure><img src="{img_url}" alt="" /></figure>')

        # Content elements
        for el in article.get("content_elements", []):
            el_type = el.get("type", "")
            if el_type == "paragraph":
                parts.append(f"<p>{el.get('content', '')}</p>")
            elif el_type == "header":
                parts.append(f"<h3>{el.get('content', '')}</h3>")
            elif el_type == "graphic" and include_images:
                resizer_url = el.get("resizer_url", "")
                if resizer_url:
                    img_url = resizer_url.split("&")[0] + "&width=800"
                    caption = el.get("description", "")
                    if caption:
                        parts.append(
                            f'<figure><img src="{img_url}" alt="" />'
                            f"<figcaption>{caption}</figcaption></figure>"
                        )
                    else:
                        parts.append(f'<figure><img src="{img_url}" alt="" /></figure>')

        # Sign-off
        sign_off = article.get("sign_off")
        if sign_off:
            parts.append(f"<p><small>{sign_off}</small></p>")

        html = "\n".join(parts)
        if _count_words(html) >= MIN_ARTICLE_WORDS:
            return html

    return None


def _fetch_sciam_feed(
    feed_cfg: FeedConfig, config: Config, cache: ContentCache | None = None
) -> Section:
    """Fetch articles from Scientific American's latest magazine issue.

    SciAm has no working RSS feed. Instead, the issue page embeds a __DATA__
    JSON script with article metadata (title, slug, author, date, category).
    Articles are freely accessible via standard trafilatura extraction.
    Feed URL should be https://www.scientificamerican.com (auto-discovers
    latest issue) or a specific issue URL like /issue/sa/2026/03-01/.
    Technique from Calibre's scientific_american.recipe by Kovid Goyal.
    """
    section = Section(name=feed_cfg.name, category=feed_cfg.category)

    try:
        articles_meta = _fetch_sciam_issue_articles(feed_cfg.url)
    except Exception:
        logger.warning("SciAm issue discovery failed for %s", feed_cfg.name, exc_info=True)
        return section

    if not articles_meta:
        logger.warning("SciAm returned no articles for %s", feed_cfg.name)
        return section

    # Build synthetic feedparser-like entries and delegate to _extract_article
    consecutive_failures = 0
    for meta in articles_meta[:_FETCH_CAP_PER_FEED]:
        slug = meta.get("slug", "")
        url = f"{_SCIAM_BASE}/article/{slug}"

        # Build author string from authors list
        authors = meta.get("authors", [])
        author = ", ".join(a.get("name", "") for a in authors if a.get("name"))

        # Synthetic feedparser entry
        entry = {
            "link": url,
            "title": meta.get("title", "Untitled"),
            "author": author or None,
            "published": meta.get("date_published"),
        }

        article = _extract_article(entry, config, cache=cache)
        if article:
            section.articles.append(article)
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                logger.info(
                    "Aborting %s after %d consecutive extraction failures",
                    feed_cfg.name,
                    consecutive_failures,
                )
                break

    return section


def _fetch_sciam_issue_articles(feed_url: str) -> list[dict]:
    """Discover articles from the latest Scientific American issue.

    Fetches the issue page (or homepage to find it), then parses the
    __DATA__ JSON script for article metadata.
    Returns list of article metadata dicts with keys:
    title, slug, authors, date_published, category, subtype.
    """
    parsed = urlparse(feed_url)
    path = parsed.path.strip("/")

    # If feed URL is a specific issue page, use it directly
    if path.startswith("issue/"):
        issue_url = f"{_SCIAM_BASE}/{path}"
    else:
        # Fetch homepage to find latest issue link
        req = urllib.request.Request(
            _SCIAM_BASE,
            headers={"User-Agent": _BROWSER_USER_AGENT},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception:
            logger.warning("SciAm homepage fetch failed", exc_info=True)
            return []

        issue_match = re.search(r'href="(/issue/sa/[^"]+)"', html)
        if not issue_match:
            logger.warning("Could not find SciAm issue link on homepage")
            return []
        issue_url = f"{_SCIAM_BASE}{issue_match.group(1)}"

    # Fetch the issue page and parse __DATA__ JSON
    req = urllib.request.Request(
        issue_url,
        headers={"User-Agent": _BROWSER_USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        logger.warning("SciAm issue page fetch failed: %s", issue_url, exc_info=True)
        return []

    script_match = re.search(
        r'<script[^>]*id="__DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if not script_match:
        logger.warning("No __DATA__ script found on SciAm issue page")
        return []

    raw = script_match.group(1)
    if "JSON.parse(`" not in raw:
        logger.warning("Unexpected __DATA__ format on SciAm issue page")
        return []

    try:
        json_str = raw.split("JSON.parse(`")[1].replace("\\\\", "\\")
        data = json.JSONDecoder().raw_decode(json_str)[0]
    except (json.JSONDecodeError, IndexError):
        logger.warning("Failed to parse SciAm __DATA__ JSON", exc_info=True)
        return []

    issue_info = data.get("initialData", {}).get("issueData", {})
    if not issue_info:
        logger.warning("No issueData in SciAm __DATA__ JSON")
        return []

    # Collect all articles across sections (features first, then rest)
    article_previews = issue_info.get("article_previews", {})
    articles: list[dict] = []

    # Features first (most substantial), then other sections
    for section_key in sorted(
        article_previews.keys(),
        key=lambda k: (not k.startswith("featur"), k),
    ):
        for article in article_previews[section_key]:
            articles.append(article)

    logger.info(
        "SciAm issue %s: %d articles discovered",
        issue_info.get("issue_date", "unknown"),
        len(articles),
    )
    return articles


def _extract_via_archive(url: str, include_images: bool) -> str | None:
    """Fetch article via archive.today and extract with trafilatura.

    Tries multiple archive.today mirror TLDs (shuffled) until one succeeds.
    Technique from Calibre's project_syndicate.recipe by unkn0wn.

    Skipped entirely on LibreSSL (macOS system Python) where archive.today
    TLS handshakes always fail, wasting ~72s per article on timeouts.
    """
    if not _HAS_MODERN_SSL:
        logger.debug("Skipping archive.today (LibreSSL incompatible): %s", url)
        return None
    clean_url = url.split("?")[0]
    tlds = list(_ARCHIVE_TLDS)
    random.shuffle(tlds)
    for tld in tlds:
        archive_url = f"https://archive.{tld}/latest/{clean_url}"
        page = _fetch_page(archive_url, _BROWSER_USER_AGENT)
        if not page:
            continue
        extracted = _trafilatura_extract_from_html(page, include_images)
        if extracted and _count_words(extracted) >= MIN_ARTICLE_WORDS:
            return extracted
    return None


def _extract_paginated_content(
    url: str, raw_page: str, include_images: bool
) -> str | None:
    """Follow pagination links and concatenate content.

    Technique from Calibre's ars_technica.recipe by Kovid Goyal.
    """
    seen = {url.rstrip("/")}
    pages = []
    for match in _PAGINATION_LINK_RE.finditer(raw_page):
        page_url = match.group(1)
        page_num = int(match.group(2))
        if page_url.startswith("/"):
            parsed = urlparse(url)
            page_url = f"{parsed.scheme}://{parsed.netloc}{page_url}"
        if page_url.rstrip("/") in seen or page_num <= 1:
            continue
        seen.add(page_url.rstrip("/"))
        pages.append((page_num, page_url))

    if not pages:
        return None

    pages.sort()
    extra = []
    for _, page_url in pages:
        page_html = _fetch_page(page_url, _BROWSER_USER_AGENT)
        if page_html:
            extracted = _trafilatura_extract_from_html(page_html, include_images)
            if extracted:
                # Strip title heading from continuation pages
                extracted = re.sub(
                    r"^\s*<h[12]\b[^>]*>.*?</h[12]>\s*", "",
                    extracted, count=1, flags=re.DOTALL | re.IGNORECASE,
                )
                extra.append(_normalize_html(extracted))
    return "\n".join(extra) if extra else None


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


class _LimitedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler with a lower limit to fail faster on redirect loops."""

    max_redirections = 5


def _fetch_page(
    url: str, user_agent: str, extra_headers: dict[str, str] | None = None
) -> str | None:
    """Download a web page and return HTML source.

    Uses a cookie jar so cookies set during redirects (e.g. Nature.com's
    idp.nature.com session cookie) persist across the redirect chain.
    Limits redirects to 5 (default is 10) and detects auth redirect loops.
    """
    if not is_safe_url(url):
        return None
    try:
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            _LimitedRedirectHandler,
            urllib.request.HTTPCookieProcessor(jar),
        )
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        if extra_headers:
            for key, val in extra_headers.items():
                req.add_header(key, val)
        with opener.open(req, timeout=15) as resp:
            # Detect auth redirect loops — if final URL landed on a login page
            final_url = resp.url or ""
            parsed_final = urlparse(final_url)
            if parsed_final.netloc.startswith("idp.") or any(
                pat in parsed_final.path for pat in _AUTH_URL_PATTERNS
            ):
                logger.debug("Auth redirect detected, aborting: %s → %s", url, final_url)
                return None
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
    consistent output. Rules applied sequentially from _NORMALIZE_RULES.
    """
    for pattern, replacement in _NORMALIZE_RULES:
        html = pattern.sub(replacement, html)
    return html.strip()


def _strip_duplicate_title(html: str, title: str) -> str:
    """Remove <h1>/<h2> from extracted HTML if it matches the article title.

    Scans ALL h1/h2 tags in the body (not just leading), removing any that
    fuzzy-match the title. This handles cases where a <figure> or other
    element precedes the title heading.
    """
    if not title or not html:
        return html

    # Normalize title for comparison (unescape HTML entities first —
    # feedparser may leave &#8217; etc. as literal strings)
    title_clean = re.sub(r"[^\w\s]", "", _html_mod.unescape(title).lower()).strip()
    if not title_clean:
        return html

    def _is_match(heading_html: str) -> bool:
        heading_text = re.sub(r"<[^>]+>", "", heading_html).strip()
        heading_clean = re.sub(
            r"[^\w\s]", "", _html_mod.unescape(heading_text).lower()
        ).strip()
        if not heading_clean:
            return False
        # Containment in both directions
        return heading_clean in title_clean or title_clean in heading_clean

    def _replace(match: re.Match) -> str:
        if _is_match(match.group(2)):
            return ""
        return match.group(0)

    return _ALL_HEADINGS_RE.sub(_replace, html)


def _downgrade_body_headings(html: str) -> str:
    """Downgrade all <h1> tags to <h2> in article body HTML.

    epub.py adds its own <h1> from Article.title, so any <h1> in the
    extracted body would create duplicate top-level headings.
    """
    html = re.sub(r"<h1\b", "<h2", html, flags=re.IGNORECASE)
    html = re.sub(r"</h1>", "</h2>", html, flags=re.IGNORECASE)
    return html


def _dedup_consecutive_paragraphs(html: str) -> str:
    """Remove consecutive duplicate block sequences.

    Detects repeated sequences of 1–4 block elements (p, h1–h6) with identical
    text content. Non-block elements (figures, divs) between blocks are skipped
    so that patterns like ``<h2>T</h2><p>S</p><figure/><h2>T</h2><p>S</p>``
    are caught (Verge subtitle duplication).

    Uses lxml for reliable DOM manipulation.
    """
    from lxml import html as lxml_html
    from lxml import etree

    doc = lxml_html.fragment_fromstring(html, create_parent="div")
    block_tags = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6"})

    # Collect block elements with their text
    blocks: list[tuple[str, object]] = []
    for child in doc:
        if child.tag in block_tags:
            text = (child.text_content() or "").strip()
            blocks.append((text, child))

    to_remove: list[object] = []
    i = 0
    while i < len(blocks):
        # Try sequence lengths 1–4 (longest first for greedy matching)
        matched = False
        for seq_len in range(min(4, (len(blocks) - i) // 2), 0, -1):
            seq_texts = [blocks[i + k][0] for k in range(seq_len)]
            next_texts = [blocks[i + seq_len + k][0] for k in range(seq_len)]
            if all(t for t in seq_texts) and seq_texts == next_texts:
                # Remove the duplicate (second occurrence)
                for k in range(seq_len):
                    to_remove.append(blocks[i + seq_len + k][1])
                i += seq_len * 2  # skip past both original + duplicate
                matched = True
                break
        if not matched:
            i += 1

    if not to_remove:
        return html
    for el in to_remove:
        el.getparent().remove(el)

    result = etree.tostring(doc, encoding="unicode", method="html")
    if result.startswith("<div>") and result.endswith("</div>"):
        result = result[5:-6]
    return result


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
    seen_urls: set[str] = set()  # deduplicate identical images

    def _replace_img(match: re.Match) -> str:
        tag = match.group(0)
        attrs = dict(_ATTR_RE.findall(tag))

        # Prefer data-src (lazy-loaded images) over src
        # Decode HTML entities (&amp; → &) — trafilatura's <graphic> tags
        # emit entity-encoded URLs that fail on CDN-signed images (e.g. Guardian 401s)
        src = _html_mod.unescape(attrs.get("data-src") or attrs.get("src", ""))
        if not src or _should_skip_image(src):
            return ""

        # Skip duplicate images within the same article
        if src in seen_urls:
            return ""
        seen_urls.add(src)

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
        # Clean internal stock photo filenames / placeholder alt text
        if alt and (_STOCK_ALT_RE.match(alt) or _FILENAME_ALT_RE.match(alt)):
            alt = ""
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

    # Flatten nested <figure> tags created when _replace_img wraps an <img>
    # that was already inside a <figure> from the source HTML
    new_html = _NESTED_FIGURE_RE.sub(r"<figure>\1\2</figure>", new_html)

    return new_html, images


def _should_skip_image(url: str) -> bool:
    """Filter out ads, tracking pixels, icons, and logos by URL."""
    parsed = urlparse(url)

    netloc = parsed.netloc
    for ad_domain in _AD_DOMAINS_FULL:
        if ad_domain in netloc:
            return True
    if netloc.startswith(_AD_SUBDOMAIN_PREFIXES):
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
