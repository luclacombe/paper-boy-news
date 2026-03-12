"""Post-extraction content filters for article quality control.

Five general-purpose filters that operate on extracted HTML:
- strip_junk(): removes boilerplate paragraphs (ads, social, newsletters)
- strip_section_junk(): removes multi-element junk sections (heading + list/content)
- strip_trailing_junk(): removes trailing metadata (wire bylines, editorial credits)
- detect_paywall(): detects paywalled/truncated articles
- check_quality(): enforces minimum quality standards
"""

from __future__ import annotations

import re

# --- Junk stripping ---

# Grouped junk patterns — each group has a category comment.
# Adding a new pattern = appending one string to the right group.
# The compiled regex is built automatically at import time.
_JUNK_PATTERN_GROUPS: list[list[str]] = [
    # --- Generic boilerplate ---
    [
        r"advertisement",
        r"share\s+this\s+article",
        r"share\s+on\s+\w+",
        r"related\s+articles?",
        r"read\s+more\s*:",
        r"more\s+from\b.*",
        r"you\s+may\s+also\s+be\s+interested\s+in",
    ],
    # --- Social / follow CTAs ---
    [
        r"follow\s+us\s+on\s+\w+.*",
        r"go\s+to\s+bbc\w*\.com\s+for\s+more\b.*",
    ],
    # --- Newsletter / subscription CTAs ---
    [
        r"sign\s+up\s+(for|to)\b.*",
        r"subscribe\s+to\s+our\s+newsletter",
        r"you\s+are\s+now\s+subscribed",
        r"your\s+newsletter\s+sign.up\s+was\s+successful",
        r"want\s+to\s+add\s+more\s+newsletters\??",
        r"enjoying\s+our\s+latest\s+content\b.*",
        r"access\s+the\s+most\s+recent\s+journalism\b.*",
        r"explore\s+the\s+latest\s+features\b.*",
        r"thank\s+you\s+for\s+visiting\s+nature\.com\b.*",
    ],
    # --- Wired / Space.com / ScienceDaily ---
    [
        r"power\s+up\s+with\s+unlimited\s+access\b.*",
        r"breaking\s+space\s+news\b.*",
        r"story\s+source:",
        r"cite\s+this\s+page:",
    ],
    # --- Fox News CTAs ---
    [
        r"click\s+here\s+to\s+(?:download|sign\s+up|get)\b.*",
        r"click\s+here\s+for\s+more\b.*",
        r"like\s+what\s+you(?:'re|.re)\s+reading\??\s*click\s+here\b.*",
        r"follow\s+fox\s+news\b.*",
    ],
    # --- Source-specific boilerplate preambles ---
    [
        r"agenda[- ]setting\s+intelligence,?\s+analysis\s+and\s+advice\b.*",  # BoF
        r"these\s+highlights\s+were\s+written\s+by\s+the\s+reporters\b.*",  # ProPublica
        r"we(?:'ve|.ve)\s+lifted\s+the\s+paywall\.?\s+foreign\s+policy(?:'s|.s)\b.*",  # Foreign Policy
        r"roula\s+khalaf,?\s+editor\s+of\s+the\s+ft,?\s+selects\b.*",  # FT
        r"get\s+your\s+daily\s+dose\s+of\s+health\b.*",  # STAT Morning Rounds
        r"good\s+morning\s+and\s+welcome\s+to\s+the\s+downshift\b.*",  # The Drive TDS
    ],
    # --- Navigation / related article CTAs ---
    [
        r"go\s+deeper\s*:.*",  # BoF
        r"learn\s+more\s*:.*",  # BoF
    ],
    # --- Guardian sign-up variant ---
    [
        r"sign\s+up\s*:.*",  # Guardian "Sign up: AU Breaking News email"
    ],
    # --- NPR / newsletter boilerplate ---
    [
        r"you(?:'re|.re)\s+reading\s+the\s+(?:up\s+first|morning)\s+newsletter\b.*",  # NPR
        r"good\s+morning\.?\s+you(?:'re|.re)\s+reading\s+the\s+(?:up\s+first|morning)\s+newsletter\b.*",  # NPR with greeting
        r"this\s+newsletter\s+was\s+edited\s+by\b.*",  # NPR
    ],
    # --- Post metadata ---
    [
        r"this\s+post\s+originally\s+published\b.*",  # TechCrunch
        r"materials\s+provided\s+by\b.*(?:note:\s+content\s+may\s+be\s+edited)?.*",  # ScienceDaily
    ],
    # --- BBC trailing solicitation ---
    [
        r"if\s+you\s+have\s+information\s+about\s+this\s+story\b.*(?:please\s+email)?.*",
    ],
    # --- AP News section links ---
    [
        r"_{3,}",  # AP horizontal rule separator (3+ underscores)
    ],
    # --- Wired engagement sections ---
    [
        r"in\s+your\s+inbox\b.*",  # Wired
        r"what\s+say\s+you\?.*",  # Wired
    ],
    # --- Kiplinger subscription/tagline ---
    [
        r"profit\s+and\s+prosper\b.*",  # Kiplinger tagline
    ],
    # --- Donation / partnership blocks ---
    [
        r"this\s+coverage\s+is\s+made\s+possible\s+through\s+a\s+partnership\b.*",  # Grist
        r"if\s+you(?:'ve|.ve)\s+ever\s+considered\s+going\s+solar\b.*",  # Electrek affiliate
    ],
    # --- Free newsletter label ---
    [
        r"free\s+newsletter",  # New Scientist standalone label
    ],
]

# Compile once at import time — same regex as before, just organized
_JUNK_PATTERNS = re.compile(
    r"^(" + "|".join(p for group in _JUNK_PATTERN_GROUPS for p in group) + r")$",
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
    r"<p>\s*(?:Story Source|Journal References?|Cite This Page)\s*:\s*</p>.*",
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


# --- Structural junk stripping (multi-element) ---

# Rules: (heading_text_pattern, scope)
# scope: "to_end" = remove heading + all siblings after
#        "to_next_heading" = remove heading + siblings until next h2/h3/h4
# Populated by future batches — empty list means no-op.
_SECTION_JUNK_RULES: list[tuple[re.Pattern, str]] = [
    # Rock Paper Shotgun "Read this next" + article list
    (re.compile(r"^Read this next$", re.IGNORECASE), "to_end"),
    # Al Jazeera "Recommended Stories" + article list
    (re.compile(r"^Recommended Stories$", re.IGNORECASE), "to_end"),
    # TechCrunch / Wired "Contact Us" / "Got a Tip?" sections
    (re.compile(r"^(?:Contact Us|Got a Tip\??)$", re.IGNORECASE), "to_next_heading"),
    # New Scientist newsletter signup blocks (h4 "Sign up to [Name]")
    (re.compile(r"^Sign up to\b", re.IGNORECASE), "to_next_heading"),
    # Inside Climate News donation block — anchored to ICN-specific phrasing
    (re.compile(r"^(?:Support Our (?:Work|Mission|Reporting)|Donate to\b)", re.IGNORECASE), "to_next_heading"),
    # Kiplinger subscription CTA sections
    (re.compile(r"^(?:Subscribe|Join)\s+(?:to|for)\s+Kiplinger", re.IGNORECASE), "to_next_heading"),
    # STAT "What we're reading" trailing list
    (re.compile(r"^What we(?:'re|.re) reading$", re.IGNORECASE), "to_end"),
]


def strip_section_junk(html: str) -> str:
    """Remove multi-element junk sections identified by heading text.

    Handles patterns that strip_junk() can't: heading + list,
    heading + multiple paragraphs, etc. Uses lxml for DOM-aware stripping.

    Returns html unchanged when _SECTION_JUNK_RULES is empty.
    """
    if not _SECTION_JUNK_RULES:
        return html

    from lxml import html as lxml_html  # lxml is installed via trafilatura

    doc = lxml_html.fragment_fromstring(html, create_parent="div")
    for pattern, scope in _SECTION_JUNK_RULES:
        for heading in doc.iter("h2", "h3", "h4"):
            text = (heading.text_content() or "").strip()
            if not pattern.match(text):
                continue
            if scope == "to_end":
                # Remove heading + all following siblings
                parent = heading.getparent()
                if parent is None:
                    continue
                remove = False
                for child in list(parent):
                    if child is heading:
                        remove = True
                    if remove:
                        parent.remove(child)
            elif scope == "to_next_heading":
                # Remove heading + siblings until next h2/h3/h4
                parent = heading.getparent()
                if parent is None:
                    continue
                to_remove = [heading]
                for sibling in heading.itersiblings():
                    if sibling.tag in ("h2", "h3", "h4"):
                        break
                    to_remove.append(sibling)
                for el in to_remove:
                    parent.remove(el)

    from lxml import etree

    result = etree.tostring(doc, encoding="unicode", method="html")
    # Strip the wrapper <div> we added
    if result.startswith("<div>") and result.endswith("</div>"):
        result = result[5:-6]
    return result


# --- Trailing junk stripping ---

# Patterns matching text of trailing elements; strips from match to end.
# Populated by future batches — empty list means no-op.
_TRAILING_JUNK_RULES: list[re.Pattern] = [
    # The Drive tip-line: "Got a tip? tips@thedrive.com"
    re.compile(r"^Got a tip\??", re.IGNORECASE),
    # BBC trailing email solicitation (multi-sentence)
    re.compile(
        r"^If you have information about this story",
        re.IGNORECASE,
    ),
    # AP News section link after separator
    re.compile(r"^AP\s+\w+:", re.IGNORECASE),
]


def strip_trailing_junk(html: str) -> str:
    """Remove trailing metadata (wire bylines, editorial credits, social handles).

    Walks the last N elements; if any match a trailing rule,
    removes from that element to the end. Uses lxml for DOM-aware stripping.

    Returns html unchanged when _TRAILING_JUNK_RULES is empty.
    """
    if not _TRAILING_JUNK_RULES:
        return html

    from lxml import html as lxml_html

    doc = lxml_html.fragment_fromstring(html, create_parent="div")
    children = list(doc)
    # Walk from the end, check last 10 elements
    cutoff = None
    for i in range(len(children) - 1, max(len(children) - 11, -1), -1):
        text = (children[i].text_content() or "").strip()
        for pattern in _TRAILING_JUNK_RULES:
            if pattern.match(text):
                cutoff = i
                break
        if cutoff is not None:
            break

    if cutoff is not None:
        for child in children[cutoff:]:
            doc.remove(child)

    from lxml import etree

    result = etree.tostring(doc, encoding="unicode", method="html")
    if result.startswith("<div>") and result.endswith("</div>"):
        result = result[5:-6]
    return result


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
