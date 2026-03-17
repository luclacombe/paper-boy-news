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
        r"partner\s+content\s+from\b.*",  # Eater sponsored content label
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
        r"we(?:'d|.d)\s+love\s+to\s+hear\s+from\s+you\b.*",  # SciAm email CTA
        r"marketing\s+brew\s+informs\s+marketing\s+pros\b.*",  # Morning Brew newsletter CTA
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
        r"roula\s+khalaf.*?selects\s+her\s+favourite\s+stories.*?newsletter.*",  # FT newsletter preamble variant
        r"this\s+article\s+is\s+an?\s+on[- ]site\s+version\s+of\s+our\b.*newsletter\b.*",  # FT on-site newsletter version
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
        r"the\s+associated\s+press(?:'|.)\s+\w+\s+(?:and\s+\w+\s+)?coverage\s+receives\s+(?:financial\s+)?support\b.*",  # AP philanthropy boilerplate
    ],
    # --- Wired engagement sections ---
    [
        r"in\s+your\s+inbox\b.*",  # Wired
        r"what\s+say\s+you\?.*",  # Wired
    ],
    # --- Kiplinger subscription/tagline ---
    [
        r"profit\s+and\s+prosper\b.*",  # Kiplinger tagline
        r"become\s+a\s+smarter.*subscribe\s+from\b.*",  # Kiplinger subscription CTA
        r".*sign\s+up\s+for\s+.*\bour\s+free\b.*\bnewsletter\b.*",  # Kiplinger newsletter CTAs (Closing Bell, Adviser Intel, etc.)
        r"about\s+adviser\s+intel$",  # Kiplinger Adviser Intel heading paragraph
        r".*\bparticipant\s+in\s+Kiplinger.s\s+Adviser\s+Intel\s+program\b.*",  # Kiplinger Adviser Intel boilerplate
        r".*\bsubscribe\s+to\s+Kiplinger.s\s+free\s+newsletter\b.*",  # Kiplinger "Subscribe to Kiplinger's free newsletter"
        r".*\bsubscribe\s+to\s+help\s+you\s+make\s+more\s+money\b.*",  # Kiplinger magazine CTA
        r".*\bKiplinger\s+chose\s+the\s+best\b.*\brewards\b.*",  # Kiplinger advertising/affiliate
        r".*\bsign\s+up\s+for\s+Kiplinger.s\b.*\bfree\b.*",  # Kiplinger newsletter sign-up variants
        r".*\bfor\s+Kiplinger\s+Personal\s+Finance\b",  # Kiplinger magazine pricing CTA
    ],
    # --- Donation / partnership blocks ---
    [
        r"this\s+coverage\s+is\s+made\s+possible\s+through\s+a\s+partnership\b.*",  # Grist
        r"if\s+you(?:'ve|.ve)\s+ever\s+considered\s+going\s+solar\b.*",  # Electrek affiliate
        r"ftc:\s+we\s+use\s+income\s+earning\s+auto\s+affiliate\s+links\b.*",  # Electrek FTC disclosure
    ],
    # --- Free newsletter label ---
    [
        r"free\s+newsletter",  # New Scientist standalone label
    ],
    # --- Space.com ad break / comment system ---
    [
        r"article\s+continues\s+below",  # Space.com mid-article ad marker
        r"(?:you\s+must\s+)?(?:confirm|enter)\s+your\s+public\s+display\s+name\b.*",  # Space.com comment system
        r"please\s+log\s*out\s+and\s+then\s+log\s*in\s+again\b.*",  # Space.com comment system variant
    ],
    # --- FT myFT Digest CTAs ---
    [
        r"simply\s+sign\s+up\s+to\s+the\b.*myft\s+digest\b.*",  # FT newsletter cross-sell
    ],
    # --- Bloomberg podcast CTA ---
    [
        r"subscribe\s+to\s+the\s+bloomberg\b.*podcast\b.*",  # Bloomberg podcast CTA
    ],
    # --- Politico Playbook CTA ---
    [
        r"like\s+this\s+content\??\s*consider\s+sign(?:ing)?\s+up\b.*",  # Politico Playbook
    ],
    # --- BoF runway gallery artifacts ---
    [
        r"\d+\s+of\s+\d+",  # "0 of 44" slideshow counter
        r"\w[\w\s]+\s+look\s+\d+\.\s*\(Launchmetrics\b.*",  # "Brand AW26 look 1. (Launchmetrics...)"
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
    # Al Jazeera "Recommended Stories" + article list (next_1 — only strip
    # the heading + the <ul> that follows, because AJ embeds this mid-article
    # with real content continuing after the list)
    (re.compile(r"^Recommended Stories$", re.IGNORECASE), "next_1"),
    # TechCrunch / Wired "Contact Us" / "Got a Tip?" sections
    (re.compile(r"^(?:Contact Us|Got a Tip\??)$", re.IGNORECASE), "to_next_heading"),
    # New Scientist newsletter signup blocks (h4 "Sign up to [Name]")
    # Use "next_3" to only remove the heading + up to 3 siblings (the typical
    # signup block: description <p> + figure + maybe a link). "to_next_heading"
    # was too aggressive — removed legitimate article content when the next
    # structural heading was far away (843 → 397 avg words regression).
    (re.compile(r"^Sign up to\b", re.IGNORECASE), "next_3"),
    # Inside Climate News donation block — anchored to ICN-specific phrasing
    (re.compile(r"^(?:Support Our (?:Work|Mission|Reporting)|Donate to\b)", re.IGNORECASE), "to_next_heading"),
    # Kiplinger subscription CTA sections
    (re.compile(r"^(?:Subscribe|Join|Sign up)\s+(?:to|for)\s+Kiplinger", re.IGNORECASE), "to_next_heading"),
    # Kiplinger "Related content" / "Read More" trailing sections
    (re.compile(r"^(?:Related content|Read More)$", re.IGNORECASE), "to_end"),
    # STAT "What we're reading" trailing list
    (re.compile(r"^What we(?:'re|.re) reading$", re.IGNORECASE), "to_end"),
    # Rolling Stone "Behind the Scenes" production credits (to_end — everything after is crew)
    (re.compile(r"^Behind the Scenes$", re.IGNORECASE), "to_end"),
    # Electrek "Top comment by [username]" (to_next_heading — reader comment, not editorial)
    (re.compile(r"^Top comment by\b", re.IGNORECASE), "to_next_heading"),
    # SciAm "On supporting science journalism" heading + subscription paragraph
    (re.compile(r"^On supporting science journalism$", re.IGNORECASE), "next_1"),
    # ICN donation block — "This story is funded by readers like you" + everything after
    (re.compile(r"^This story is funded by readers like you\.?$", re.IGNORECASE), "to_end"),
    # ICN "About This Story" trailing section
    (re.compile(r"^About This Story$", re.IGNORECASE), "to_end"),
    # Morning Brew newsletter CTA — heading + up to 2 elements (description + branding)
    (re.compile(r"^Get marketing news you.ll actually want to read$", re.IGNORECASE), "next_2"),
    # Kiplinger subscription heading + block
    (re.compile(r"^From just\b.*Kiplinger\b", re.IGNORECASE), "next_2"),
    # FT "Recommended newsletters for you" footer — everything after is promo
    (re.compile(r"^Recommended newsletters?\s+for\s+you$", re.IGNORECASE), "to_end"),
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
            elif scope.startswith("next_"):
                # Remove heading + up to N following siblings (bounded strip).
                # Safer than "to_next_heading" when junk blocks appear
                # mid-article — won't accidentally consume real content.
                limit = int(scope.split("_", 1)[1])
                parent = heading.getparent()
                if parent is None:
                    continue
                to_remove = [heading]
                for count, sibling in enumerate(heading.itersiblings()):
                    if count >= limit:
                        break
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
    # Wire byline tails: "Reporting by X; editing by Y"
    re.compile(r"^(?:Reporting|Writing|Compiled)\s+by\b", re.IGNORECASE),
    # Wire "Edited by: Name"
    re.compile(r"^Edited\s+by:?\s+\w", re.IGNORECASE),
    # Wire "Additional reporting by"
    re.compile(r"^Additional\s+reporting\s+by\b", re.IGNORECASE),
    # AP author bio + social links
    re.compile(r"^\w[\w\s]+ writes (?:about|for|on)\b.+(?:the AP|Associated Press)\b", re.IGNORECASE),
    # PetaPixel "Image credits:"
    re.compile(r"^Image\s+credits?:", re.IGNORECASE),
    # Space.com author bio
    re.compile(r"^\w[\w\s.]+ is Space\.com.s\b", re.IGNORECASE),
    # Correction notes
    re.compile(r"^Correction:", re.IGNORECASE),
    # BoF standalone byline: "By Name, Name" — case-sensitive to avoid "By all accounts..."
    re.compile(r"^By\s+[A-Z][a-z]+(?:(?:\s+(?:and\s+)?|,\s*)[A-Z][a-z.'-]+)*$"),
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
        # Skip non-element nodes (HTML comments, processing instructions).
        # HtmlComment.tag is a callable, not a string — use that to detect.
        if not isinstance(children[i].tag, str):
            continue
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


# --- Lede dedup (Reuters pattern) ---


def strip_lede_dupe(html: str) -> str:
    """Remove duplicate lede paragraph that repeats an opening <em> block.

    Reuters mobile API produces: <em>Summary</em> <small>By Author</small>
    <p>Summary</p> (duplicate). This strips the duplicate <p> when its text
    matches the preceding <em> text.

    General-purpose: safe for all sources since it only fires when the first
    meaningful element is <em> and a near-identical <p> follows within the
    first 5 block elements.
    """
    try:
        from lxml import html as lxml_html
    except ImportError:
        return html

    try:
        doc = lxml_html.fragment_fromstring(html, create_parent="div")
    except Exception:
        return html

    # Find the first <em> — either as a direct child or inside the first <p>.
    # Reuters pattern: <p><em>Summary</em></p> <p><small>By Author</small></p> <p>Summary</p>
    first_em = None
    em_parent = None  # The block-level element containing the <em>
    for el in doc:
        if el.tag == "em":
            first_em = el
            em_parent = el
            break
        if el.tag == "p":
            # Check if this <p> contains only an <em> child (possibly with tail whitespace)
            children = list(el)
            if len(children) == 1 and children[0].tag == "em":
                em_only = not (el.text or "").strip()
                if em_only:
                    first_em = children[0]
                    em_parent = el
                    break
            break  # First <p> doesn't have the pattern — stop
        if el.tag in ("h1", "h2", "h3", "h4", "h5", "h6", "figure", "div", "ul", "ol"):
            break

    if first_em is None:
        return html

    em_text = (first_em.text_content() or "").strip().lower()
    if not em_text or len(em_text) < 20:
        return html

    # Scan siblings after the em_parent for a <p> with matching text.
    # Skip metadata elements like <p><small>By Author</small></p>.
    count = 0
    for sibling in em_parent.itersiblings():
        count += 1
        if count > 5:
            break
        if sibling.tag != "p":
            continue
        # Skip <p> containing only <small> (byline metadata)
        children = list(sibling)
        if children and all(c.tag == "small" for c in children) and not (sibling.text or "").strip():
            continue
        p_text = (sibling.text_content() or "").strip().lower()
        if not p_text or len(p_text) < 20:
            continue  # Skip short metadata paragraphs (bylines, dates)
        # Fuzzy match: one contains the other (handles minor differences)
        if em_text in p_text or p_text in em_text:
            sibling.getparent().remove(sibling)
            from lxml import etree
            result = etree.tostring(doc, encoding="unicode", method="html")
            # Strip the wrapper <div> we added
            if result.startswith("<div>") and result.endswith("</div>"):
                result = result[5:-6]
            return result
        break  # First substantial <p> didn't match — stop

    return html


# --- Figcaption-to-paragraph dedup (NPR pattern) ---


def strip_figcaption_paragraph_dupe(html: str) -> str:
    """Remove <p> elements that duplicate the preceding <figcaption> text.

    NPR articles produce: <figure>...<figcaption>Caption</figcaption></figure>
    <p>Caption. Photographer/Agency</p>. The <p> starts with the figcaption
    text and appends a photo credit.

    General-purpose: safe for all sources since it only fires when a <p>
    immediately following a </figure> starts with that figure's figcaption text.
    """
    try:
        from lxml import html as lxml_html
        from lxml import etree
    except ImportError:
        return html

    try:
        doc = lxml_html.fragment_fromstring(html, create_parent="div")
    except Exception:
        return html

    modified = False
    # Find all <figure> elements and check the sibling after each
    for figure in doc.iter("figure"):
        # Get figcaption text
        figcaption = figure.find(".//figcaption")
        if figcaption is None:
            continue
        caption_text = (figcaption.text_content() or "").strip().lower()
        if not caption_text or len(caption_text) < 10:
            continue

        # Check next sibling — must be a <p>
        next_el = figure.getnext()
        if next_el is None or next_el.tag != "p":
            continue

        p_text = (next_el.text_content() or "").strip().lower()
        if p_text and p_text.startswith(caption_text):
            next_el.getparent().remove(next_el)
            modified = True

    if not modified:
        return html

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
    r"|this\s+is\s+a\s+preview\s+of\s+subscription\s+content"
    r"|exclusive\s+to\s+\w+\+?\s+subscribers"
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


# --- HTML sanitization for EPUB output ---

# Safe tags for e-reader EPUB content
_SANITIZE_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "img", "figure", "figcaption",
    "a", "em", "strong", "b", "i", "u",
    "ul", "ol", "li",
    "blockquote", "table", "tr", "td", "th", "thead", "tbody",
    "br", "hr",
    "span", "div", "small", "sub", "sup",
    "dl", "dt", "dd",
}

_SANITIZE_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href", "title"},
    "img": {"src", "alt", "width", "height"},
    "*": {"class", "id"},
}


def sanitize_html(html: str) -> str:
    """Sanitize HTML for safe EPUB inclusion.

    Strips <script>, <style>, <iframe>, <object>, <embed>, event handlers,
    javascript: URIs, and data: URIs on src attributes.
    """
    if not html:
        return html

    try:
        import nh3
    except ImportError:
        # Graceful fallback: strip the most dangerous patterns manually
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<iframe[^>]*>.*?</iframe>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<object[^>]*>.*?</object>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<embed[^>]*>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"\bon\w+\s*=", "", html, flags=re.IGNORECASE)
        html = re.sub(r"javascript:", "", html, flags=re.IGNORECASE)
        return html

    return nh3.clean(
        html,
        tags=_SANITIZE_TAGS,
        attributes=_SANITIZE_ATTRIBUTES,
        url_schemes={"http", "https"},
    )
