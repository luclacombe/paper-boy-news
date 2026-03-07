"""Reusable card components for Paper Boy."""

from typing import List, Optional

import streamlit as st

from web.components.theme import (
    CAPTION_GRAY,
    DELIVERED_GREEN,
    BUILDING_AMBER,
    FAILED_CHARCOAL,
    EDITION_RED,
)


def status_banner(
    status: str,
    message: str,
    detail: str = "",
):
    """Render a status banner (delivered, building, failed, empty).

    Args:
        status: One of "delivered", "building", "failed", "empty".
        message: Primary status message.
        detail: Secondary detail line (e.g., "37 articles - 8 sources - 2.4 MB").
    """
    status_styles = {
        "delivered": {
            "border_color": DELIVERED_GREEN,
            "icon": "&#10003;",
            "icon_color": DELIVERED_GREEN,
        },
        "building": {
            "border_color": BUILDING_AMBER,
            "icon": "&#9676;",
            "icon_color": BUILDING_AMBER,
        },
        "failed": {
            "border_color": FAILED_CHARCOAL,
            "icon": "&#10007;",
            "icon_color": FAILED_CHARCOAL,
        },
        "empty": {
            "border_color": CAPTION_GRAY,
            "icon": "&#9671;",
            "icon_color": CAPTION_GRAY,
        },
    }
    style = status_styles.get(status, status_styles["empty"])

    detail_html = ""
    if detail:
        detail_html = f'<div class="mono-text" style="margin-top: 0.25rem;">{detail}</div>'

    st.html(
        f"""
    <div class="status-banner" style="border-left: 4px solid {style['border_color']};">
        <div style="font-size: 1.1rem; font-weight: 600; color: {style['icon_color']};">
            <span style="margin-right: 0.5rem;">{style['icon']}</span>
            {message}
        </div>
        {detail_html}
    </div>
    """
    )


def headline_card(source_name: str, headlines: List[str], source_type: str = "RSS"):
    """Render a headline card for a single source.

    Args:
        source_name: Name of the source (e.g., "The Guardian").
        headlines: List of article titles (shows first 2-3).
        source_type: "RSS" or "Newsletter".
    """
    headlines_html = ""
    for title in headlines[:3]:
        headlines_html += f"""
        <div class="headline-text" style="font-size: 0.95rem; margin-bottom: 0.4rem;">
            {title}
        </div>
        """

    remaining = len(headlines) - 3
    if remaining > 0:
        headlines_html += f"""
        <div class="caption-text" style="margin-top: 0.3rem;">
            &middot;&middot;&middot; {remaining} more article{"s" if remaining != 1 else ""}
        </div>
        """

    type_badge = ""
    if source_type == "Newsletter":
        type_badge = '<span class="section-label" style="float: right; font-size: 0.7rem;">newsletter</span>'

    st.html(
        f"""
    <div class="pb-card">
        <div class="section-label" style="margin-bottom: 0.5rem;">
            {source_name}
            {type_badge}
        </div>
        <hr class="thin-rule" style="margin-bottom: 0.6rem;">
        {headlines_html}
    </div>
    """
    )


def source_card(
    name: str,
    url: str,
    article_count: Optional[int] = None,
    last_fetched: str = "",
    status: str = "active",
):
    """Render a source card for the Sources page.

    Args:
        name: Source name.
        url: Feed URL.
        article_count: Number of articles fetched.
        last_fetched: When the feed was last fetched.
        status: "active" or "warning".
    """
    badge_class = "badge-active" if status == "active" else "badge-failed"
    badge_text = "Active" if status == "active" else "Warning"
    badge_icon = "&#10003;" if status == "active" else "&#9888;"

    stats_parts = []
    if article_count is not None:
        stats_parts.append(f'<span class="mono-text">{article_count} articles</span>')
    if last_fetched:
        stats_parts.append(f'<span class="caption-text">Last fetched: {last_fetched}</span>')

    stats_html = ""
    if stats_parts:
        stats_html = f'<div style="margin-top: 0.5rem;">{" &middot; ".join(stats_parts)}</div>'

    st.html(
        f"""
    <div class="pb-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <div class="headline-text" style="font-size: 1rem;">{name}</div>
                <div class="caption-text" style="font-size: 0.8rem; margin-top: 0.15rem;">{url}</div>
            </div>
            <span class="badge {badge_class}">{badge_icon} {badge_text}</span>
        </div>
        {stats_html}
    </div>
    """
    )


def edition_card(
    date_str: str,
    edition_number: int,
    article_count: int,
    source_count: int,
    file_size: str,
    status: str,
    delivery_method: str = "",
    error_message: str = "",
):
    """Render an edition card for the Editions page.

    Args:
        date_str: Formatted date string.
        edition_number: Edition number.
        article_count: Number of articles.
        source_count: Number of sources.
        file_size: File size string (e.g., "2.4 MB").
        status: "delivered", "failed", or "building".
        delivery_method: How the edition was delivered (e.g., "google_drive", "email", "local").
        error_message: Error message if failed.
    """
    badge_class = {
        "delivered": "badge-delivered",
        "failed": "badge-failed",
        "building": "badge-building",
    }.get(status, "badge-failed")

    badge_text = {
        "delivered": "&#10003; Delivered",
        "failed": "&#10007; Failed",
        "building": "&#9676; Building",
    }.get(status, status)

    error_html = ""
    if error_message:
        error_html = f'<div class="caption-text" style="margin-top: 0.3rem; color: #C23B22;">{error_message}</div>'

    # Stats line
    stats_parts = []
    if article_count:
        stats_parts.append(f"{article_count} articles")
    if source_count:
        stats_parts.append(f"{source_count} sources")
    if file_size:
        stats_parts.append(file_size)
    stats_line = " &middot; ".join(stats_parts)

    # Delivery method label
    method_label = ""
    if delivery_method and status == "delivered":
        method_map = {
            "google_drive": "Google Drive",
            "email": "Email",
            "local": "Downloaded",
        }
        method_label = method_map.get(delivery_method, delivery_method)

    right_html = f'<span class="badge {badge_class}">{badge_text}</span>'
    if edition_number:
        right_html += f'<div class="caption-text" style="margin-top: 0.2rem;">Edition #{edition_number}</div>'
    if method_label:
        right_html += f'<div class="caption-text" style="margin-top: 0.15rem; font-size: 0.75rem;">via {method_label}</div>'

    st.html(
        f"""
    <div class="pb-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <div class="headline-text" style="font-size: 1rem;">{date_str}</div>
                <div class="mono-text" style="margin-top: 0.2rem;">{stats_line}</div>
                {error_html}
            </div>
            <div style="text-align: right;">
                {right_html}
            </div>
        </div>
    </div>
    """
    )


def device_card(device_name: str, svg_icon: str, selected: bool = False):
    """Render a device selection card with halftone-style SVG illustration.

    The card is made clickable via an invisible Streamlit button overlay
    (see theme.py CSS for .device-select-card).
    """
    card_class = "pb-card pb-card-clickable device-select-card"
    if selected:
        card_class += " pb-card-selected"

    st.html(
        f"""
    <div class="{card_class}" style="text-align: center; padding: 1.5rem 0.75rem; min-height: 180px;
         display: flex; flex-direction: column; align-items: center; justify-content: center;">
        <div style="margin-bottom: 0.5rem;">{svg_icon}</div>
        <div class="headline-text" style="font-size: 1rem;">{device_name}</div>
    </div>
    """
    )


def bundle_card(name: str, description: str, selected: bool = False):
    """Render a selectable bundle card with visual feedback.

    The card is made clickable via an invisible Streamlit button overlay
    (see theme.py CSS for .bundle-select-card).
    """
    card_class = "pb-card pb-card-clickable bundle-select-card"
    if selected:
        card_class += " pb-card-selected"

    st.html(
        f"""
    <div class="{card_class}" style="text-align: center; padding: 1.25rem;">
        <div class="headline-text" style="font-size: 0.95rem; margin-bottom: 0.5rem;">
            {name}
        </div>
        <div class="caption-text" style="font-size: 0.8rem;">
            {description}
        </div>
    </div>
    """
    )
