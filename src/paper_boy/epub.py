"""EPUB generation with proper metadata for e-reader organization."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

from ebooklib import epub

from paper_boy.config import Config
from paper_boy.cover import generate_cover
from paper_boy.feeds import IMG_PLACEHOLDER_PREFIX, Section

# CSS optimized for e-reader displays (Kobo, Kindle, reMarkable)
# Avoids CSS Grid/Flexbox, complex selectors, and custom fonts (poorly supported)
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
p {
    margin: 0.6em 0;
    text-align: justify;
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
    color: #666;
    margin-bottom: 1em;
    font-style: italic;
}
.article-meta .author {
    font-weight: bold;
    font-style: normal;
}
.article-source {
    font-size: 0.75em;
    color: #999;
    margin-top: 2em;
    padding-top: 0.5em;
    border-top: 1px solid #ddd;
}
.section-title {
    font-size: 1.6em;
    text-align: center;
    margin: 2em 0 1em 0;
    padding: 0.5em 0;
    border-top: 3px solid #333;
    border-bottom: 1px solid #999;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}
.toc-section {
    margin: 1em 0 0.3em 0;
    font-weight: bold;
    font-size: 1.1em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #333;
}
.toc-article {
    margin: 0.2em 0 0.2em 1em;
}
.toc-article a {
    text-decoration: none;
    color: #1a1a1a;
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
    color: #666;
    font-style: italic;
    margin-top: 0.3em;
    text-align: center;
    padding: 0 1em;
}
blockquote {
    margin: 1em 1.5em;
    font-style: italic;
    border-left: 3px solid #ccc;
    padding-left: 1em;
    color: #333;
}
"""


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
        filename = f"paper-boy-{date_str}.epub"
        output_path = Path(filename)
    else:
        output_path = Path(output_path)

    book = epub.EpubBook()

    # --- Metadata ---
    uid = f"paper-boy-{issue_date.isoformat()}-{uuid.uuid4().hex[:8]}"
    book.set_identifier(uid)
    book.set_title(f"{config.newspaper.title} — {issue_date.strftime('%B %d, %Y')}")
    book.set_language(config.newspaper.language)
    book.add_author("Paper Boy")

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

    # --- Build chapters ---
    spine_items: list[str | epub.EpubHtml] = ["nav"]
    toc_sections = []
    all_chapters = []
    article_index = 0

    # Front page / custom TOC page
    front_page = _build_front_page(sections, issue_date, config)
    front_page.add_item(css)
    book.add_item(front_page)
    spine_items.append(front_page)

    for section_idx, section in enumerate(sections):
        if not section.articles:
            continue

        # Section divider page
        divider = _build_section_divider(section, section_idx)
        divider.add_item(css)
        book.add_item(divider)
        spine_items.append(divider)

        section_chapters = []

        for article in section.articles:
            article_index += 1
            chapter = _build_article_chapter(article, article_index, section.name)
            chapter.add_item(css)

            # Embed article images into the EPUB
            for img_idx, img in enumerate(article.images):
                filename = f"images/article_{article_index:03d}_{img_idx + 1:02d}.jpg"
                uid = f"article_{article_index:03d}_img_{img_idx + 1:02d}"

                epub_img = epub.EpubImage(
                    uid=uid,
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
            all_chapters.append(chapter)

        # Add section to TOC with nested articles
        toc_sections.append(
            (epub.Section(section.name), section_chapters)
        )

    # --- Table of Contents ---
    book.toc = toc_sections

    # --- Navigation files ---
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # --- Spine (reading order) ---
    book.spine = spine_items

    # --- Write ---
    epub.write_epub(str(output_path), book)
    return output_path


def _build_front_page(
    sections: list[Section], issue_date: date, config: Config
) -> epub.EpubHtml:
    """Build a front page with a table of contents listing."""
    date_str = issue_date.strftime("%A, %B %d, %Y")

    html_parts = [
        f'<h1 style="text-align:center; border-bottom: 2px solid #333; '
        f'padding-bottom: 0.3em;">{config.newspaper.title}</h1>',
        f'<p style="text-align:center; color:#666; font-style:italic;">{date_str}</p>',
        "<hr/>",
    ]

    article_index = 0
    for section in sections:
        if not section.articles:
            continue
        html_parts.append(f'<p class="toc-section">{section.name}</p>')
        for article in section.articles:
            article_index += 1
            html_parts.append(
                f'<p class="toc-article">'
                f'<a href="article_{article_index:03d}.xhtml">{article.title}</a>'
                f"</p>"
            )

    front = epub.EpubHtml(
        title="Front Page",
        file_name="front_page.xhtml",
        lang=config.newspaper.language,
    )
    front.content = "\n".join(html_parts).encode("utf-8")
    return front


def _build_section_divider(section: Section, section_idx: int) -> epub.EpubHtml:
    """Build a section divider page."""
    html = f'<div class="section-title">{section.name}</div>'

    divider = epub.EpubHtml(
        title=section.name,
        file_name=f"section_{section_idx:02d}.xhtml",
    )
    divider.content = html.encode("utf-8")
    return divider


def _build_article_chapter(article, article_index: int, section_name: str) -> epub.EpubHtml:
    """Build an article page."""
    meta_parts = []
    if article.author:
        meta_parts.append(f'<span class="author">{article.author}</span>')
    if article.date:
        meta_parts.append(article.date)
    meta_line = " &middot; ".join(meta_parts) if meta_parts else ""

    html = f"""<h1>{article.title}</h1>
<p class="article-meta">{meta_line}</p>
<div class="article-body">
{article.html_content}
</div>
<p class="article-source">Source: {article.url}</p>"""

    chapter = epub.EpubHtml(
        title=article.title,
        file_name=f"article_{article_index:03d}.xhtml",
    )
    chapter.content = html.encode("utf-8")
    return chapter
