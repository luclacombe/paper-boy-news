"""EPUB generation with proper metadata for e-reader organization."""

from __future__ import annotations

import email.utils
import random
import uuid
from collections import OrderedDict
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from ebooklib import epub
from PIL import Image

from paper_boy.config import Config
from paper_boy.cover import generate_cover
from paper_boy.feeds import IMG_PLACEHOLDER_PREFIX, Section
from paper_boy.filters import sanitize_html

# CSS optimized for e-reader displays (Kobo, Kindle, reMarkable)
# Avoids CSS Grid/Flexbox, complex selectors, and custom fonts (poorly supported)
# Minimum gray = #555 for e-ink readability
STYLESHEET = """
body {
    font-family: serif;
    font-size: 1.05em;
    line-height: 1.7;
    margin: 1em;
    color: #1a1a1a;
}
h1 {
    font-size: 1.4em;
    margin-bottom: 0.3em;
    line-height: 1.2;
}
h2 {
    font-size: 1.2em;
    margin-bottom: 0.2em;
}
h3 {
    font-size: 1.1em;
    margin: 1em 0 0.3em;
}
h4 {
    font-size: 1.05em;
    margin: 0.8em 0 0.2em;
}
h5 {
    font-size: 1em;
    font-weight: bold;
    margin: 0.6em 0 0.2em;
}
h6 {
    font-size: 0.95em;
    font-weight: bold;
    font-style: italic;
    margin: 0.6em 0 0.2em;
}
p {
    margin: 0.6em 0;
    text-align: justify;
}
hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 1em 3em;
}
.article-body > p:first-child {
    text-indent: 0;
}
.article-body > p {
    text-indent: 1.5em;
    margin-top: 0.2em;
    margin-bottom: 0.2em;
}
.article-meta {
    font-size: 0.85em;
    color: #444;
    margin-bottom: 1em;
    font-style: italic;
}
.article-meta .author {
    font-weight: bold;
    font-style: normal;
}
.article-source {
    font-size: 0.75em;
    color: #555;
    margin-top: 1.5em;
    padding-top: 0.5em;
    border-top: 1px solid #555;
}
.front-title {
    text-align: center;
    padding-bottom: 0.3em;
}
.front-date {
    text-align: center;
    color: #444;
    font-style: italic;
    margin-bottom: 1.5em;
}
.section-title {
    font-size: 0.85em;
    text-align: center;
    margin: 0.2em 0 0.1em 0;
    padding: 0;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #555;
    font-weight: normal;
}
.toc-category {
    margin: 2em 0 0.3em 0;
    font-weight: bold;
    font-size: 1.5em;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #1a1a1a;
    border-bottom: 2px solid #333;
    padding-bottom: 0.2em;
}
.toc-section {
    margin: 1.2em 0 0.3em 0;
    font-size: 1em;
    font-weight: bold;
    font-style: italic;
    color: #333;
}
.toc-article {
    margin: 0.15em 0 0.15em 1.2em;
    text-indent: -0.8em;
    padding-left: 0.8em;
}
.toc-article a {
    text-decoration: none;
    color: #1a1a1a;
}
.category-divider {
    margin-top: 5%;
    text-align: center;
    page-break-before: always;
}
.category-rule-top {
    border-top: 3px solid #333;
    width: 60%;
    margin: 0 auto 0.6em;
}
.category-rule-bottom {
    border-top: 1px solid #555;
    width: 60%;
    margin: 0.3em auto;
}
.category-name {
    font-size: 2.2em;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    font-weight: bold;
}
.category-sources {
    font-size: 1.1em;
    color: #444;
    margin-top: 1.5em;
    text-align: center;
    letter-spacing: 0.03em;
}
.category-sources a {
    text-decoration: none;
    color: #444;
}
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0.5em auto;
}
figure {
    margin: 1em 0;
    padding: 0;
    text-align: center;
    page-break-inside: avoid;
    break-inside: avoid;
}
figure img {
    max-width: 100%;
    height: auto;
}
figcaption {
    font-size: 0.8em;
    color: #444;
    font-style: italic;
    margin-top: 0.3em;
    text-align: center;
    padding: 0 1em;
}
blockquote {
    margin: 1em 1.5em;
    font-style: italic;
    border-left: 3px solid #555;
    padding-left: 1em;
    color: #222;
}
"""


def _group_sections_by_category(
    sections: list[Section],
) -> list[tuple[str, list[Section]]]:
    """Group sections by category, preserving insertion order.

    Empty or "Custom" categories are grouped under "Other" at the end.
    If ALL sections have empty category (CLI mode), returns a single
    group with empty string key — callers skip category dividers.
    """
    # Check if any section has a category
    has_categories = any(
        s.category and s.category != "Custom" for s in sections if s.articles
    )
    if not has_categories:
        return [("", [s for s in sections if s.articles])]

    groups: OrderedDict[str, list[Section]] = OrderedDict()
    other: list[Section] = []

    for section in sections:
        if not section.articles:
            continue
        cat = section.category
        if not cat or cat == "Custom":
            other.append(section)
        else:
            groups.setdefault(cat, []).append(section)

    if other:
        groups["Other"] = groups.get("Other", []) + other

    return list(groups.items())


def build_epub(
    sections: list[Section],
    config: Config,
    issue_date: date | None = None,
    output_path: str | Path | None = None,
) -> Path:
    """Build a newspaper EPUB from extracted sections.

    Returns the path to the generated EPUB file.
    """
    if issue_date is None:
        issue_date = date.today()

    if output_path is None:
        date_str = issue_date.strftime("%Y-%m-%d")
        base = Path(f"paper-boy-{date_str}.epub")
        if base.exists():
            # Auto-increment to avoid overwriting previous builds
            n = 2
            while True:
                candidate = Path(f"paper-boy-{date_str}-build{n}.epub")
                if not candidate.exists():
                    break
                n += 1
            output_path = candidate
        else:
            output_path = base
    else:
        output_path = Path(output_path)

    book = epub.EpubBook()

    # --- Metadata ---
    uid = f"paper-boy-{issue_date.isoformat()}-{uuid.uuid4().hex[:8]}"
    book.set_identifier(uid)
    book.set_title(f"{config.newspaper.title} — {issue_date.strftime('%B %d, %Y')}")
    book.set_language(config.newspaper.language)
    book.add_author("Paper Boy News")

    # Publication date
    book.add_metadata("DC", "date", issue_date.isoformat())

    # Calibre series metadata — Kobo reads this with NickelSeries mod
    # Groups all issues as a series in the library, sorted by date
    if getattr(config.delivery, "device", "kobo") == "kobo":
        book.add_metadata(
            None, "meta", "", {"name": "calibre:series", "content": config.newspaper.title}
        )
        book.add_metadata(
            None,
            "meta",
            "",
            {
                "name": "calibre:series_index",
                "content": issue_date.strftime("%Y%m%d"),
            },
        )

    # EPUB3 series metadata (standard)
    book.add_metadata(
        None,
        "meta",
        config.newspaper.title,
        {"property": "belongs-to-collection", "id": "series-id"},
    )
    book.add_metadata(
        None, "meta", "series", {"refines": "#series-id", "property": "collection-type"}
    )
    book.add_metadata(
        None,
        "meta",
        issue_date.strftime("%Y%m%d"),
        {"refines": "#series-id", "property": "group-position"},
    )

    # --- Cover ---
    cover_bytes = generate_cover(config.newspaper.title, sections, issue_date)
    book.set_cover("cover.jpg", cover_bytes)

    # --- Stylesheet ---
    css = epub.EpubItem(
        uid="style",
        file_name="style/default.css",
        media_type="text/css",
        content=STYLESHEET.encode("utf-8"),
    )
    book.add_item(css)

    # --- Logo (resized for e-reader inline use) ---
    logo_file = Path(__file__).parent / "assets" / "pb_logo.png"
    logo_filename: str | None = None
    if logo_file.exists():
        logo_filename = "images/pb_logo.png"
        with Image.open(logo_file) as logo_im:
            logo_im.thumbnail((120, 120), Image.LANCZOS)
            buf = BytesIO()
            logo_im.save(buf, format="PNG")
            logo_bytes = buf.getvalue()
        logo_img = epub.EpubImage(
            uid="pb_logo",
            file_name=logo_filename,
            media_type="image/png",
            content=logo_bytes,
        )
        book.add_item(logo_img)

    # --- Group sections by category ---
    category_groups = _group_sections_by_category(sections)
    has_categories = len(category_groups) > 1 or (
        len(category_groups) == 1 and category_groups[0][0] != ""
    )

    # --- Cover page (explicit, for proper opening behavior) ---
    cover_page = epub.EpubHtml(
        title="Cover",
        file_name="cover_page.xhtml",
        lang=config.newspaper.language,
    )
    cover_page.content = (
        '<div style="text-align:center; margin:0; padding:0;">'
        '<img src="cover.jpg" alt="Cover" style="max-width:100%; height:auto;" />'
        '</div>'
    ).encode("utf-8")
    cover_page.add_item(css)
    book.add_item(cover_page)

    # --- Pre-compute first-article file for each section (for divider links) ---
    section_first_files: dict[int, str] = {}
    _counter = 0
    for _, _cat_secs in category_groups:
        for _sec in _cat_secs:
            if _sec.articles:
                section_first_files[id(_sec)] = f"article_{_counter + 1:03d}.xhtml"
                _counter += len(_sec.articles)

    # --- Build chapters ---
    spine_items: list[str | tuple[epub.EpubHtml, str] | epub.EpubHtml] = [(cover_page, "no")]
    toc_entries = []
    article_index = 0
    category_divider_idx = 0

    # Front page / custom TOC page
    front_page = _build_front_page(
        sections, issue_date, config, category_groups, has_categories,
        section_first_files=section_first_files,
    )
    front_page.add_item(css)
    book.add_item(front_page)
    spine_items.append(front_page)

    num_categories = len(category_groups)
    for cat_idx, (cat_name, cat_sections) in enumerate(category_groups):
        # Category divider page (skip when no categories)
        if has_categories:
            prev_href = "front_page.xhtml" if cat_idx == 0 else f"category_{cat_idx - 1:02d}.xhtml"
            next_href = f"category_{cat_idx + 1:02d}.xhtml" if cat_idx < num_categories - 1 else None
            cat_divider = _build_category_divider(
                cat_name, category_divider_idx, cat_sections,
                section_first_files=section_first_files,
                logo_filename=logo_filename,
                prev_href=prev_href,
                next_href=next_href,
            )
            cat_divider.add_item(css)
            book.add_item(cat_divider)
            spine_items.append(cat_divider)
            category_divider_idx += 1

        all_cat_chapters = []  # Flat list for 2-level TOC
        cat_toc_children = []  # Source-grouped for no-category mode

        for section in cat_sections:
            if not section.articles:
                continue

            section_start = article_index + 1  # index the first article will get
            section_count = len(section.articles)
            section_chapters = []

            for article_idx, article in enumerate(section.articles):
                article_index += 1
                chapter = _build_article_chapter(
                    article, article_index, section.name,
                    section_heading=section.name if article_idx == 0 else None,
                    section_article_count=section_count,
                    section_start_index=section_start,
                )
                chapter.add_item(css)

                # Embed article images into the EPUB
                for img_idx, img in enumerate(article.images):
                    filename = f"images/article_{article_index:03d}_{img_idx + 1:02d}.jpg"
                    img_uid = f"article_{article_index:03d}_img_{img_idx + 1:02d}"

                    epub_img = epub.EpubImage(
                        uid=img_uid,
                        file_name=filename,
                        media_type="image/jpeg",
                        content=img.data,
                    )
                    book.add_item(epub_img)

                    # Replace placeholder in chapter HTML with actual EPUB path
                    placeholder = f"{IMG_PLACEHOLDER_PREFIX}{img_idx}__"
                    chapter.content = chapter.content.replace(
                        placeholder.encode("utf-8"), filename.encode("utf-8")
                    )

                book.add_item(chapter)
                spine_items.append(chapter)
                section_chapters.append(chapter)

            all_cat_chapters.extend(section_chapters)

            # Build TOC entry for no-category mode (source-level nesting)
            if section_chapters:
                section_link = epub.Link(
                    section_chapters[0].file_name, section.name, section_chapters[0].id
                )
                cat_toc_children.append(
                    (section_link, section_chapters)
                )

        # 2-level TOC: category → articles (avoids 3-level rendering bugs)
        if has_categories and all_cat_chapters:
            cat_link = epub.Link(
                cat_divider.file_name, cat_name, cat_divider.id
            )
            toc_entries.append((cat_link, all_cat_chapters))
        else:
            toc_entries.extend(cat_toc_children)

    # --- TOC: add "Start" entry linking to front page ---
    start_link = epub.Link("front_page.xhtml", config.newspaper.title, "front_page")
    toc_entries.insert(0, start_link)

    # --- End page ---
    end_page = _build_end_page(config, logo_filename=logo_filename)
    end_page.add_item(css)
    book.add_item(end_page)
    spine_items.append(end_page)

    # --- Table of Contents ---
    book.toc = toc_entries

    # --- Navigation files ---
    book.add_item(epub.EpubNcx())

    # Nav document — ebooklib generates TOC + landmarks from book.guide
    nav = epub.EpubNav()
    nav.add_item(css)
    book.add_item(nav)

    # --- Spine (reading order) ---
    book.spine = spine_items

    # --- Guide / Landmarks (EPUB2 compat + EPUB3 bodymatter) ---
    # Point bodymatter to front page so e-readers open to the TOC
    book.guide = [
        {"type": "cover", "title": "Cover", "href": "cover_page.xhtml"},
        {"type": "toc", "title": "Table of Contents", "href": "front_page.xhtml"},
        {"type": "text", "title": "Start of Content", "href": "front_page.xhtml"},
    ]

    # --- Write ---
    opts = {"epub3_landmark": True}
    epub.write_epub(str(output_path), book, opts)
    return output_path


def _build_front_page(
    sections: list[Section],
    issue_date: date,
    config: Config,
    category_groups: list[tuple[str, list[Section]]],
    has_categories: bool,
    section_first_files: dict[int, str] | None = None,
) -> epub.EpubHtml:
    """Build a front page with a table of contents listing."""
    date_str = issue_date.strftime("%A, %B %d, %Y")

    html_parts = [
        f'<h1 class="front-title">{config.newspaper.title}</h1>',
        f'<p class="front-date">{date_str}</p>',
        '<p style="text-align:center; font-size:0.75em; color:#888;'
        ' letter-spacing:0.1em; margin-top:0.8em;">'
        '\u2014 Tap to jump to any section \u2014</p>',
    ]

    article_index = 0
    cat_divider_idx = 0
    for cat_name, cat_sections in category_groups:
        if has_categories:
            cat_href = f"category_{cat_divider_idx:02d}.xhtml"
            html_parts.append(
                f'<h2 class="toc-category">'
                f'<a href="{cat_href}" style="text-decoration:none; color:inherit;">'
                f'{cat_name}</a></h2>'
            )
            cat_divider_idx += 1

        for section in cat_sections:
            if not section.articles:
                continue
            first_file = section_first_files.get(id(section)) if section_first_files else None
            if first_file:
                html_parts.append(
                    f'<p class="toc-section">'
                    f'<a href="{first_file}" style="text-decoration:none; color:inherit;">'
                    f'{section.name}</a></p>'
                )
            else:
                html_parts.append(f'<p class="toc-section">{section.name}</p>')
            for article in section.articles:
                article_index += 1
                html_parts.append(
                    f'<p class="toc-article">'
                    f'\u25b8 <a href="article_{article_index:03d}.xhtml">{article.title}</a>'
                    f"</p>"
                )

    front = epub.EpubHtml(
        title="Front Page",
        file_name="front_page.xhtml",
        lang=config.newspaper.language,
    )
    front.content = "\n".join(html_parts).encode("utf-8")
    return front


def _build_category_divider(
    category_name: str, idx: int, cat_sections: list[Section],
    section_first_files: dict[int, str] | None = None,
    logo_filename: str | None = None,
    prev_href: str | None = None,
    next_href: str | None = None,
) -> epub.EpubHtml:
    """Build a category divider page with centered layout and linked sources."""
    # Build source links (or plain text if no file mapping)
    source_parts = []
    for s in cat_sections:
        if not s.articles:
            continue
        first_file = section_first_files.get(id(s)) if section_first_files else None
        if first_file:
            source_parts.append(f'<a href="{first_file}">{s.name}</a>')
        else:
            source_parts.append(s.name)
    feed_names = f" \u2009\u00b7\u2009 ".join(source_parts)

    logo_html = ""
    if logo_filename:
        logo_html = (
            f'<a href="front_page.xhtml">'
            f'<img src="{logo_filename}" alt=""'
            ' width="40" height="40"'
            ' style="display:block; margin:35% auto 0;" />'
            '</a>'
        )

    # Navigation links — left/right aligned via table (e-reader safe)
    link_style = "text-decoration:none; color:#888;"
    nav_html = ""
    if prev_href or next_href:
        back_label = "Contents" if prev_href == "front_page.xhtml" else "Previous"
        left = (
            f'<a href="{prev_href}" style="{link_style}">\u25c2 {back_label}</a>'
            if prev_href else ""
        )
        right = (
            f'<a href="{next_href}" style="{link_style}">Next \u25b8</a>'
            if next_href else ""
        )
        nav_html = (
            '<table style="width:80%; margin:1.5em auto 0; border:none;'
            ' border-collapse:collapse; font-size:0.85em;">'
            '<tr>'
            f'<td style="text-align:left; border:none; padding:0;">{left}</td>'
            f'<td style="text-align:right; border:none; padding:0;">{right}</td>'
            '</tr></table>'
        )

    html = (
        '<div class="category-divider">'
        '<div class="category-rule-top"></div>'
        f'<div class="category-name">{category_name.upper()}</div>'
        '<div class="category-rule-bottom"></div>'
        f'<p class="category-sources" style="margin-top:15%;">{feed_names}</p>'
        f'{logo_html}'
        f'{nav_html}'
        '</div>'
    )

    divider = epub.EpubHtml(
        title=category_name,
        file_name=f"category_{idx:02d}.xhtml",
    )
    divider.content = html.encode("utf-8")
    return divider



def _format_article_date(date_str: str) -> str:
    """Normalize article date to human-readable format (e.g. 'March 7, 2026').

    Tries RFC 2822 (RSS dates) and ISO 8601. Falls back to raw string.
    """
    # Try RFC 2822 (e.g. "Fri, 07 Mar 2026 12:00:00 GMT")
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        return dt.strftime("%B %-d, %Y")
    except (ValueError, TypeError):
        pass

    # Try ISO 8601 (e.g. "2026-03-07T12:00:00Z")
    try:
        # Handle trailing Z
        cleaned = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.strftime("%B %-d, %Y")
    except (ValueError, TypeError):
        pass

    return date_str


def _build_article_chapter(
    article, article_index: int, section_name: str,
    section_heading: str | None = None,
    section_article_count: int = 1,
    section_start_index: int = 0,
) -> epub.EpubHtml:
    """Build an article page.

    When ``section_heading`` is provided (first article of a source), the
    source name is rendered as a heading above the article title so the reader
    sees the source context without a standalone divider page.
    """
    meta_parts = []
    if article.author:
        meta_parts.append(f'<span class="author">{article.author}</span>')
    if article.date:
        meta_parts.append(_format_article_date(article.date))
    meta_line = " &middot; ".join(meta_parts) if meta_parts else ""

    # Show domain instead of full URL
    domain = urlparse(article.url).netloc.removeprefix("www.")

    # Sanitize article body HTML to strip <script>, event handlers, etc.
    safe_content = sanitize_html(article.html_content) if article.html_content else ""

    # Source name + article position dots on every article
    section_header = (
        f'<div class="section-title">'
        f'\u25c6 {section_name} \u25c6</div>\n'
    )
    if section_article_count > 1 and section_start_index > 0:
        dots = []
        for i in range(section_article_count):
            idx = section_start_index + i
            href = f"article_{idx:03d}.xhtml"
            if idx == article_index:
                dots.append('<span style="color:#333;">\u25cf</span>')
            else:
                dots.append(
                    f'<a href="{href}" style="text-decoration:none;'
                    f' color:#999;">\u25cb</a>'
                )
        dot_html = " \u2009 ".join(dots)
        section_header += (
            f'<p style="text-align:center; font-size:0.75em;'
            f' margin:0 0 0.4em; letter-spacing:0.2em;">{dot_html}</p>\n'
        )

    html = f"""{section_header}<h1>{article.title}</h1>
<p class="article-meta">{meta_line}</p>
<div class="article-body">
{safe_content}
</div>
<p class="article-source">via {domain}</p>"""

    chapter = epub.EpubHtml(
        title=article.title,
        file_name=f"article_{article_index:03d}.xhtml",
    )
    chapter.content = html.encode("utf-8")
    return chapter


_END_PAGE_SIGN_OFFS = [
    ("That\u2019s the end of today\u2019s edition.", "See you tomorrow morning."),
    ("End of edition.", "We\u2019ll have more tomorrow."),
    ("Did you learn something new today?", "We hope so. See you tomorrow."),
    ("That\u2019s a wrap.", "Same time tomorrow?"),
    ("You made it to the back page.", "Not everyone reads this far."),
    ("Another edition, another day informed.", "Tomorrow brings more."),
    ("What was the best story today?", "We\u2019ll have new ones tomorrow."),
    (
        "Finished already?",
        "We\u2019ll make tomorrow\u2019s edition longer."
        " (Just kidding... you have to change that in settings.)",
    ),
    ("End of today\u2019s paper.", "Go talk about what you read."),
    ("Well read, well informed.", "See you at tomorrow\u2019s edition."),
    ("That\u2019s everything for today.", "The world doesn\u2019t stop. Neither do we."),
    ("Paper\u2019s done. Coffee\u2019s not.", "Enjoy both."),
    ("Nothing left but the crossword.", "Oh wait, we don\u2019t have one. Yet."),
    ("You\u2019re all caught up.", "Go start your day."),
    ("Hopefully there was some good news in there.", "If not, there\u2019s always tomorrow."),
    ("Was today\u2019s news okay?", "Don\u2019t answer that. See you tomorrow."),
]


def _build_end_page(
    config: Config, logo_filename: str | None = None,
) -> epub.EpubHtml:
    """Build an end-of-edition page with a randomly selected sign-off."""
    line1, line2 = random.choice(_END_PAGE_SIGN_OFFS)

    logo_html = ""
    if logo_filename:
        logo_html = (
            f'<a href="front_page.xhtml">'
            f'<img src="{logo_filename}" alt="Paper Boy"'
            ' width="50" height="50"'
            ' style="display:block; margin:0 auto 0.8em;" />'
            '</a>'
        )

    html = (
        '<div style="margin-top:15%; text-align:center;">'
        '<div style="border-top:1px solid #999; width:30%; margin:0 auto 1.2em;"></div>'
        f'<p style="font-size:1.05em; font-style:italic; color:#333;'
        f' text-align:center; margin:0 0 0.3em;">{line1}</p>'
        f'<p style="font-size:1.05em; font-style:italic; color:#333;'
        f' text-align:center; margin:0;">{line2}</p>'
        '<div style="border-top:1px solid #999; width:30%; margin:1.2em auto 0;"></div>'
        '</div>'
        '<div style="margin-top:30%; text-align:center;">'
        f'{logo_html}'
        '<p style="font-size:0.75em; color:#888; margin:0;'
        ' text-align:center; letter-spacing:0.1em; text-transform:uppercase;">'
        '| <a href="front_page.xhtml" style="text-decoration:none;'
        ' color:#888;">Paper Boy News</a> |</p>'
        '</div>'
    )

    page = epub.EpubHtml(
        title="End",
        file_name="end_page.xhtml",
        lang=config.newspaper.language,
    )
    page.content = html.encode("utf-8")
    return page


