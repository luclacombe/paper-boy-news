"""Branded HTML email template for ebook delivery."""

from __future__ import annotations

from html import escape as _escape

# Paper Boy News color palette
_NEWSPRINT = "#f0e8d0"
_INK = "#1a1008"
_WARM_GRAY = "#ddd5c0"
_RULE_GRAY = "#a09080"
_CAPTION = "#6b5e50"
_EDITION_RED = "#8B2500"

# Shared email wrapper — newspaper broadsheet aesthetic
_WRAPPER_START = f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background-color:{_NEWSPRINT};font-family:Georgia,'Times New Roman',serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_NEWSPRINT};">
<tr><td align="center" style="padding:40px 16px;">
<table role="presentation" width="520" cellpadding="0" cellspacing="0" style="max-width:520px;width:100%;">

  <!-- Top rule (thick) -->
  <tr><td style="border-top:4px solid {_INK};padding:0;font-size:0;line-height:0;">&nbsp;</td></tr>
  <tr><td style="border-top:1px solid {_INK};padding:0;font-size:0;line-height:0;">&nbsp;</td></tr>

  <!-- Masthead -->
  <tr><td style="padding:16px 0 12px;text-align:center;">
    <h1 style="margin:0;font-size:32px;font-weight:900;color:{_INK};letter-spacing:2px;text-transform:uppercase;font-family:'Palatino Linotype',Palatino,Georgia,serif;">
      Paper Boy News
    </h1>
    <p style="margin:4px 0 0;font-size:11px;color:{_CAPTION};letter-spacing:3px;text-transform:uppercase;">
      Your morning edition, set in type
    </p>
  </td></tr>

  <!-- Bottom rule -->
  <tr><td style="border-top:1px solid {_INK};border-bottom:3px double {_INK};padding:0;font-size:0;line-height:0;">&nbsp;</td></tr>
"""

_WRAPPER_END = f"""\
  <!-- Footer rule -->
  <tr><td style="border-top:1px solid {_RULE_GRAY};padding:20px 0 0;text-align:center;">
    <p style="margin:0;font-size:11px;color:{_CAPTION};line-height:1.5;font-style:italic;">
      <a href="https://www.paper-boy-news.com" style="color:{_CAPTION};text-decoration:none;">
        www.paper-boy-news.com
      </a>
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def render_delivery_email(
    title: str,
    edition_date: str,
    article_count: int,
    source_count: int,
) -> str:
    """Render a newspaper-style HTML email for EPUB delivery.

    Args:
        title: Newspaper title (e.g. "Morning Digest").
        edition_date: Human-readable date (e.g. "March 18, 2026").
        article_count: Number of articles in the edition.
        source_count: Number of sources in the edition.
    """
    # Stats line (only if we have data)
    if article_count > 0:
        stats = (
            f'{article_count} article{"s" if article_count != 1 else ""} from '
            f'{source_count} source{"s" if source_count != 1 else ""}'
        )
    else:
        stats = "Fresh off the press"

    return f"""\
{_WRAPPER_START}
  <!-- Content -->
  <tr><td style="padding:28px 0 8px;text-align:center;">
    <p style="margin:0;font-size:24px;font-weight:700;color:{_INK};font-family:'Palatino Linotype',Palatino,Georgia,serif;">
      {_escape(title)}
    </p>
    <p style="margin:6px 0 0;font-size:13px;color:{_CAPTION};font-style:italic;">
      {_escape(edition_date)}
    </p>
  </td></tr>

  <!-- Thin rule -->
  <tr><td style="padding:12px 40px;"><div style="border-top:1px solid {_WARM_GRAY};"></div></td></tr>

  <!-- Body -->
  <tr><td style="padding:4px 0 20px;text-align:center;">
    <p style="margin:0 0 8px;font-size:16px;line-height:1.7;color:{_INK};">
      Good morning. Your edition is attached, {stats.lower()}.
    </p>
    <p style="margin:0;font-size:16px;line-height:1.7;color:{_INK};">
      Happy reading.
    </p>
  </td></tr>

  <!-- Settings link -->
  <tr><td style="padding:0 0 20px;text-align:center;">
    <p style="margin:0;font-size:13px;line-height:1.6;color:{_CAPTION};">
      Manage your sources, schedule, and reading time from your
      <a href="https://www.paper-boy-news.com/settings" style="color:{_EDITION_RED};text-decoration:underline;">dashboard</a>.
    </p>
  </td></tr>

{_WRAPPER_END}"""
