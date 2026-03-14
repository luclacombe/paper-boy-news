#!/usr/bin/env python3
"""Standardized EPUB stats extraction for build audits.

Extracts per-article and per-source stats from an unzipped Paper Boy EPUB.
Outputs JSON to stdout for consumption by the build-audit skill.

Usage:
    python audit/epub_stats.py <epub_dir> <build_date>
    python audit/epub_stats.py /tmp/epub-audit/epub-contents/EPUB/ 2026-03-14

EPUB article HTML structure (from epub.py):
    <h1>Title</h1>
    <p class="article-meta"><span class="author">Name</span> · Month Day, Year</p>
    <div class="article-body">
        <p>...</p>
        <figure><img src="..." alt="..."/><figcaption>...</figcaption></figure>
        ...
    </div>
    <p class="article-source">via domain.com</p>

No nested <div> tags exist inside article-body.
Word count includes all visible text (paragraphs, figcaptions, alt text, list items, blockquotes).
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# --- Regex patterns ---
# These match the exact HTML output from epub.py._build_article_chapter()

# Date: appears after author span + " · " or standalone in article-meta
# Handles: "· March 14, 2026" or bare "March 14, 2026" (no author)
RE_DATE = re.compile(
    r'<p class="article-meta">(?:<span class="author">[^<]*</span>\s*·\s*)?'
    r"([A-Z][a-z]+ \d{1,2}, \d{4})"
    r"</p>"
)

# Source domain: always "via domain.com" (no www prefix)
RE_SOURCE = re.compile(r'<p class="article-source">via ([^<]+)</p>')

# Article body: single <div class="article-body">...</div> per file, no nested divs
RE_BODY = re.compile(
    r'<div class="article-body">(.*?)</div>\s*<p class="article-source">',
    re.DOTALL,
)

# Strip HTML tags for word counting
RE_TAGS = re.compile(r"<[^>]+>")

# Count <img tags (self-closing or not)
RE_IMG = re.compile(r"<img\s")

# Article title
RE_TITLE = re.compile(r"<h1>([^<]+)</h1>")


def parse_date_bucket(date_str: str | None, build_date: datetime) -> str:
    """Classify a date string into a freshness bucket relative to build date."""
    if not date_str:
        return "NoDate"
    try:
        article_date = datetime.strptime(date_str, "%B %d, %Y")
    except ValueError:
        return "NoDate"

    delta = (build_date - article_date).days
    if delta == 0:
        return "Today"
    elif delta == 1:
        return "Yest"
    elif delta == 2:
        return "2d"
    elif 3 <= delta <= 7:
        return "3-7d"
    elif delta > 7:
        return "7d+"
    else:
        # Future date (rare but possible with timezone differences)
        return "Today"


def count_words(html_body: str) -> int:
    """Count words in article body HTML by stripping tags and splitting."""
    text = RE_TAGS.sub(" ", html_body)
    # Collapse whitespace and decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    words = text.split()
    return len(words)


def extract_article(filepath: Path, build_date: datetime) -> dict | None:
    """Extract stats from a single article XHTML file."""
    content = filepath.read_text(encoding="utf-8")

    # Source domain
    source_match = RE_SOURCE.search(content)
    if not source_match:
        return None
    source = source_match.group(1)

    # Date
    date_match = RE_DATE.search(content)
    date_str = date_match.group(1) if date_match else None
    bucket = parse_date_bucket(date_str, build_date)

    # Word count from article body
    body_match = RE_BODY.search(content)
    words = count_words(body_match.group(1)) if body_match else 0

    # Image count
    images = len(RE_IMG.findall(content))

    # Title
    title_match = RE_TITLE.search(content)
    title = title_match.group(1) if title_match else filepath.stem

    return {
        "file": filepath.name,
        "source": source,
        "date": date_str,
        "bucket": bucket,
        "words": words,
        "images": images,
        "title": title,
    }


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <epub_dir> <build_date YYYY-MM-DD>", file=sys.stderr)
        sys.exit(1)

    epub_dir = Path(sys.argv[1])
    build_date = datetime.strptime(sys.argv[2], "%Y-%m-%d")

    if not epub_dir.is_dir():
        print(f"Error: {epub_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Find all article files
    article_files = sorted(epub_dir.glob("article_*.xhtml"))
    if not article_files:
        print(f"Error: no article_*.xhtml files found in {epub_dir}", file=sys.stderr)
        sys.exit(1)

    # Extract per-article stats
    articles = []
    for f in article_files:
        article = extract_article(f, build_date)
        if article:
            articles.append(article)

    # Aggregate per-source
    source_articles = defaultdict(list)
    for a in articles:
        source_articles[a["source"]].append(a)

    sources = {}
    for source, arts in sorted(source_articles.items()):
        word_counts = [a["words"] for a in arts]
        sorted_words = sorted(word_counts)
        n = len(sorted_words)
        median = (
            sorted_words[n // 2]
            if n % 2 == 1
            else (sorted_words[n // 2 - 1] + sorted_words[n // 2]) // 2
        )

        buckets = defaultdict(int)
        for a in arts:
            buckets[a["bucket"]] += 1

        sources[source] = {
            "articles": n,
            "avg_words": round(sum(word_counts) / n) if n else 0,
            "median_words": median,
            "min_words": min(word_counts) if word_counts else 0,
            "max_words": max(word_counts) if word_counts else 0,
            "total_images": sum(a["images"] for a in arts),
            "date_buckets": dict(buckets),
            "short_articles": sum(1 for w in word_counts if w < 100),
        }

    result = {
        "build_date": sys.argv[2],
        "total_articles": len(articles),
        "total_images": sum(a["images"] for a in articles),
        "sources": sources,
        "articles": articles,
    }

    json.dump(result, sys.stdout, indent=2)
    print(file=sys.stdout)  # trailing newline


if __name__ == "__main__":
    main()
