"""Branded HTML email template for ebook delivery."""

from __future__ import annotations

from html import escape as _escape


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
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background-color:#FAF8F5;font-family:Georgia,'Times New Roman',serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#FAF8F5;">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">

  <!-- Masthead -->
  <tr><td style="border-top:3px solid #1B1B1B;border-bottom:1px solid #1B1B1B;padding:16px 0;text-align:center;">
    <h1 style="margin:0;font-size:28px;font-weight:700;color:#1B1B1B;letter-spacing:0.5px;">
      {_escape(title)}
    </h1>
    <p style="margin:6px 0 0;font-size:13px;color:#888;font-style:italic;">
      {_escape(edition_date)}
    </p>
  </td></tr>

  <!-- Body -->
  <tr><td style="padding:28px 0 24px;">
    <p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:#1B1B1B;">
      Your newspaper is attached.
    </p>
    <p style="margin:0;font-size:14px;line-height:1.6;color:#555;">
      {article_count} article{"s" if article_count != 1 else ""} from
      {source_count} source{"s" if source_count != 1 else ""}
    </p>
  </td></tr>

  <!-- Divider -->
  <tr><td style="border-top:1px solid #ddd;padding:20px 0 0;">
    <p style="margin:0;font-size:12px;color:#999;line-height:1.5;">
      Delivered by <a href="https://www.paper-boy-news.com" style="color:#999;text-decoration:underline;">Paper Boy News</a>
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


## _escape is imported from html.escape (stdlib) — handles &, <, >, ", and '
