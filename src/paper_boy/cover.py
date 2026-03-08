"""Cover image generation for the newspaper EPUB."""

from __future__ import annotations

import logging
import textwrap
from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from paper_boy.feeds import Section

logger = logging.getLogger(__name__)

# Cover dimensions optimized for e-readers
COVER_WIDTH = 600
COVER_HEIGHT = 900

# Colors
BG_COLOR = "#FAFAF8"
TEXT_COLOR = "#1A1A1A"
ACCENT_COLOR = "#333333"
RULE_COLOR = "#888888"
MUTED_COLOR = "#555555"
SECTION_COLOR = "#888888"
LEAD_RULE_COLOR = "#C83232"  # Red accent for lead story rule

# Layout constants
MARGIN = 40
INNER_MARGIN = 50

# Bundled font path (Playfair Display, OFL-licensed variable font)
_BUNDLED_FONT = Path(__file__).parent / "fonts" / "PlayfairDisplay.ttf"


def _load_font(
    size: int, weight: str = "Regular"
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load the bundled Playfair Display font at the given size and weight.

    Falls back to system serif fonts, then to Pillow's built-in default.
    The bundled font is a variable-weight TTF supporting Regular through Black.
    """
    # Try bundled font first (works on all platforms including CI)
    if _BUNDLED_FONT.exists():
        try:
            font = ImageFont.truetype(str(_BUNDLED_FONT), size)
            try:
                font.set_variation_by_name(weight)
            except Exception:
                pass  # Older Pillow or non-variable font — use default weight
            return font
        except (OSError, IOError):
            pass

    # Fallback to system fonts
    system_fonts = [
        "/System/Library/Fonts/NewYork.ttf",
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    ]
    for path in system_fonts:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue

    logger.warning("No TrueType font found — cover will use bitmap fallback")
    return ImageFont.load_default()


def _draw_double_rule(
    draw: ImageDraw.ImageDraw, y: int, x_start: int, x_end: int
) -> int:
    """Draw a thick + thin double rule. Returns the y position after the rule."""
    draw.line([(x_start, y), (x_end, y)], fill=ACCENT_COLOR, width=3)
    draw.line([(x_start, y + 5), (x_end, y + 5)], fill=ACCENT_COLOR, width=1)
    return y + 10


def _draw_text_centered(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
) -> int:
    """Draw centered text. Returns the y position after the text."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (COVER_WIDTH - text_width) // 2
    draw.text((x, y), text, fill=fill, font=font)
    return y + text_height


def _wrap_and_draw(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
    max_width: int,
    max_lines: int = 3,
    line_spacing: int = 4,
    centered: bool = False,
) -> int:
    """Word-wrap text to fit max_width and draw it. Returns y after last line."""
    # Estimate chars per line from font metrics
    avg_char_width = draw.textlength("x", font=font)
    wrap_width = max(10, int(max_width / avg_char_width))
    wrapped = textwrap.fill(text, width=wrap_width)
    lines = wrapped.split("\n")[:max_lines]

    for line in lines:
        line_bbox = draw.textbbox((0, 0), line, font=font)
        line_height = line_bbox[3] - line_bbox[1]
        if centered:
            line_width = line_bbox[2] - line_bbox[0]
            x = (COVER_WIDTH - line_width) // 2
        else:
            x = INNER_MARGIN
        draw.text((x, y), line, fill=fill, font=font)
        y += line_height + line_spacing

    return y


def generate_cover(
    title: str,
    sections: list[Section],
    issue_date: date | None = None,
) -> bytes:
    """Generate a newspaper-style cover image.

    Layout inspired by broadsheet front pages:
    - Double-rule masthead with title and date
    - Lead headline displayed prominently
    - Secondary headlines grouped by section
    - Thin rules between sections

    Returns JPEG bytes (600x900px).
    """
    if issue_date is None:
        issue_date = date.today()

    img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Load fonts at different sizes and weights
    date_font = _load_font(14, "Regular")
    tagline_font = _load_font(11, "Regular")
    lead_font = _load_font(26, "Bold")
    headline_font = _load_font(15, "SemiBold")
    section_font = _load_font(10, "Medium")

    # Scale masthead font to fit within margins
    usable_masthead = COVER_WIDTH - 2 * MARGIN
    masthead_size = 46
    masthead_font = _load_font(masthead_size, "ExtraBold")
    title_w = draw.textlength(title, font=masthead_font)
    while title_w > usable_masthead and masthead_size > 20:
        masthead_size -= 2
        masthead_font = _load_font(masthead_size, "ExtraBold")
        title_w = draw.textlength(title, font=masthead_font)

    y = MARGIN

    # === Masthead ===

    # Top double rule
    y = _draw_double_rule(draw, y, MARGIN, COVER_WIDTH - MARGIN)
    y += 16

    # Newspaper title (centered, large)
    y = _draw_text_centered(draw, y, title, masthead_font, TEXT_COLOR)
    y += 8

    # Date line (centered)
    date_str = issue_date.strftime("%A, %B %d, %Y")
    y = _draw_text_centered(draw, y, date_str, date_font, MUTED_COLOR)
    y += 4

    # Tagline
    y = _draw_text_centered(draw, y, "Your daily briefing", tagline_font, SECTION_COLOR)
    y += 10

    # Bottom double rule
    y = _draw_double_rule(draw, y, MARGIN, COVER_WIDTH - MARGIN)
    y += 20

    # === Lead headline (first article from first section) ===
    all_articles = [
        (section.name, article)
        for section in sections
        for article in section.articles[:1]
    ]

    if all_articles:
        lead_section, lead_article = all_articles[0]

        # Section label for lead
        label = lead_section.upper()
        draw.text((INNER_MARGIN, y), label, fill=LEAD_RULE_COLOR, font=section_font)
        y += 16

        # Lead headline in large text
        usable_width = COVER_WIDTH - 2 * INNER_MARGIN
        y = _wrap_and_draw(
            draw, y, lead_article.title, lead_font, TEXT_COLOR,
            max_width=usable_width, max_lines=3, line_spacing=6,
        )
        y += 8

        # Red accent rule below lead
        draw.line(
            [(INNER_MARGIN, y), (INNER_MARGIN + 80, y)],
            fill=LEAD_RULE_COLOR, width=2,
        )
        y += 20

        # === Secondary headlines ===
        remaining = all_articles[1:]
        max_secondary = 6
        drawn = 0

        for section_name, article in remaining:
            if drawn >= max_secondary or y > COVER_HEIGHT - 100:
                break

            # Thin separator
            if drawn > 0:
                draw.line(
                    [(INNER_MARGIN, y), (COVER_WIDTH - INNER_MARGIN, y)],
                    fill="#DDDDDD", width=1,
                )
                y += 10

            # Section label
            label = section_name.upper()
            draw.text((INNER_MARGIN, y), label, fill=SECTION_COLOR, font=section_font)
            y += 14

            # Headline
            y = _wrap_and_draw(
                draw, y, article.title, headline_font, TEXT_COLOR,
                max_width=usable_width, max_lines=2, line_spacing=3,
            )
            y += 8
            drawn += 1

    # === Footer ===

    # Bottom double rule
    footer_y = COVER_HEIGHT - MARGIN
    draw.line(
        [(MARGIN, footer_y - 5), (COVER_WIDTH - MARGIN, footer_y - 5)],
        fill=ACCENT_COLOR, width=1,
    )
    draw.line(
        [(MARGIN, footer_y), (COVER_WIDTH - MARGIN, footer_y)],
        fill=ACCENT_COLOR, width=3,
    )

    # Output as JPEG
    output = BytesIO()
    img.save(output, format="JPEG", quality=90)
    return output.getvalue()
