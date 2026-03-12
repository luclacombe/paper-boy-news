"""Post-extraction content filters for article quality control.

Three general-purpose filters that operate on extracted HTML:
- strip_junk(): removes boilerplate paragraphs (ads, social, newsletters)
- detect_paywall(): detects paywalled/truncated articles
- check_quality(): enforces minimum quality standards
"""

from __future__ import annotations

import re

# --- Junk stripping ---

# Patterns that match entire paragraph content (case-insensitive).
# Each pattern is anchored to match the full stripped text of a <p>/<div>.
_JUNK_PATTERNS = re.compile(
    r"^("
    r"advertisement"
    r"|follow\s+us\s+on\s+\w+.*"
    r"|go\s+to\s+bbc\w*\.com\s+for\s+more\b.*"
    r"|share\s+this\s+article"
    r"|share\s+on\s+\w+"
    r"|sign\s+up\s+(for|to)\b.*"
    r"|subscribe\s+to\s+our\s+newsletter"
    r"|related\s+articles?"
    r"|you\s+may\s+also\s+be\s+interested\s+in"
    r"|more\s+from\b.*"
    r"|read\s+more\s*:"
    r"|enjoying\s+our\s+latest\s+content\b.*"
    r"|access\s+the\s+most\s+recent\s+journalism\b.*"
    r"|explore\s+the\s+latest\s+features\b.*"
    r"|thank\s+you\s+for\s+visiting\s+nature\.com\b.*"
    # Wired subscription CTA
    r"|power\s+up\s+with\s+unlimited\s+access\b.*"
    # Space.com newsletter boilerplate
    r"|breaking\s+space\s+news\b.*"
    r"|you\s+are\s+now\s+subscribed"
    r"|your\s+newsletter\s+sign.up\s+was\s+successful"
    r"|want\s+to\s+add\s+more\s+newsletters\??"
    # ScienceDaily inline labels (caught as <p> blocks)
    r"|story\s+source:"
    r"|cite\s+this\s+page:"
    # Fox News all-caps CTAs
    r"|click\s+here\s+to\s+(?:download|sign\s+up|get)\b.*"
    r"|click\s+here\s+for\s+more\b.*"
    r"|like\s+what\s+you(?:'re|.re)\s+reading\??\s*click\s+here\b.*"
    # Fox News sports/follow CTAs
    r"|follow\s+fox\s+news\b.*"
    r")$",
    re.IGNORECASE | re.DOTALL,
)

# Match <p>...</p> or <div>...</div> blocks
_BLOCK_RE = re.compile(
    r"<(p|div)\b[^>]*>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Strip HTML tags for text-only comparison
_TAG_RE = re.compile(r"<[^>]+>")


def strip_junk(html: str) -> str:
    """Remove boilerplate paragraphs (ads, social CTAs, newsletter signups).

    Only removes <p>/<div> blocks whose entire text content matches a junk
    pattern. Does NOT strip paragraphs that merely mention these phrases
    in longer context.
    """
    def _should_remove(match: re.Match) -> str:
        inner_html = match.group(2)
        text = _TAG_RE.sub("", inner_html).strip()
        if _JUNK_PATTERNS.match(text):
            return ""
        return match.group(0)

    return _BLOCK_RE.sub(_should_remove, html)


# --- ScienceDaily metadata stripping ---

# Matches <ul> blocks containing ScienceDaily metadata fields
_SCIENCEDAILY_META_RE = re.compile(
    r"<ul\b[^>]*>(?:(?!</?ul\b).)*?<li>Date:</li>(?:(?!</?ul\b).)*?<li>Source:</li>(?:(?!</?ul\b).)*?</ul>",
    re.IGNORECASE | re.DOTALL,
)

# Matches "Story Source:" or "Journal Reference:" <p> tags and everything
# after them until the end of .article-body (these are always trailing metadata)
_SCIENCEDAILY_TRAILING_RE = re.compile(
    r"<p>\s*(?:Story Source|Journal Reference|Cite This Page)\s*:\s*</p>.*",
    re.IGNORECASE | re.DOTALL,
)


def strip_sciencedaily_metadata(html: str) -> str:
    """Remove ScienceDaily metadata (Date/Source/Summary lists and trailing refs)."""
    html = _SCIENCEDAILY_META_RE.sub("", html)
    html = _SCIENCEDAILY_TRAILING_RE.sub("", html)
    return html


# --- BBC "Related topics" section ---

# BBC Sport/News appends a "Related topics" <h2> followed by a <ul> of links
# with images, dates, and article cards. Strip the heading and everything after.
_BBC_RELATED_RE = re.compile(
    r"<h2[^>]*>\s*Related\s+topics?\s*</h2>.*",
    re.IGNORECASE | re.DOTALL,
)


def strip_bbc_related(html: str) -> str:
    """Remove BBC 'Related topics' trailing sections."""
    return _BBC_RELATED_RE.sub("", html)


# --- Paywall detection ---

_PAYWALL_PHRASES = re.compile(
    r"("
    r"log\s+in\s+to\s+continue"
    r"|log\s+in\s+or\s+create\s+an\s+account"
    r"|sign\s+in\s+to\s+continue"
    r"|subscribe\s+to\s+read"
    r"|subscribe\s+for\s+full\s+access"
    r"|subscribe\s+to\s+continue"
    r"|subscribe\s+to\s+unlock"
    r"|this\s+article\s+is\s+for\s+subscribers"
    r"|this\s+content\s+is\s+available\s+to\s+subscribers"
    r"|register\s+for\s+free"
    r"|create\s+a\s+free\s+account\s+to\s+continue"
    r")",
    re.IGNORECASE,
)

# Short-URL truncation indicator (Project Syndicate pattern):
# last <p> or <a> contains only a short URL
_SHORT_URL_DOMAINS = ("prosyn.org", "bit.ly", "tinyurl.com", "t.co", "ow.ly")
_LAST_BLOCK_RE = re.compile(
    r"<(?:p|a)\b[^>]*>([^<]*)</(?:p|a)>\s*$",
    re.IGNORECASE,
)


def detect_paywall(html: str, url: str = "") -> bool:
    """Return True if article appears to be paywalled or truncated.

    Checks for common paywall phrases and truncation indicators
    (short URLs as the last element, indicating a "read more" link).
    """
    text = _TAG_RE.sub(" ", html)
    if _PAYWALL_PHRASES.search(text):
        return True

    # Check for truncation: last block is just a short URL
    last_match = _LAST_BLOCK_RE.search(html)
    if last_match:
        last_text = last_match.group(1).strip()
        if last_text and any(domain in last_text.lower() for domain in _SHORT_URL_DOMAINS):
            return True

    return False


# --- Quality gate ---

MIN_CLEAN_WORDS = 200

_CORRECTION_RE = re.compile(
    r"^\s*(correction|author\s+correction)\s*:",
    re.IGNORECASE,
)


def check_quality(html: str) -> bool:
    """Return True if article should be REJECTED (fails quality check).

    Runs AFTER strip_junk(). Checks:
    - Minimum word count (200 words post-cleaning)
    - Correction-only articles (< 100 words starting with "Correction:")
    """
    text = _TAG_RE.sub(" ", html)
    words = text.split()
    word_count = len(words)

    if word_count < MIN_CLEAN_WORDS:
        return True

    # Correction-only articles
    if _CORRECTION_RE.match(text.strip()) and word_count < 100:
        return True

    return False
