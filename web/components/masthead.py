"""Compact newspaper header + navigation for Paper Boy."""

from datetime import date
from typing import Optional

import streamlit as st


# Navigation items with their page file paths
NAV_ITEMS = [
    {"label": "Home", "page": "pages/dashboard.py", "key": "dashboard"},
    {"label": "Sources", "page": "pages/sources.py", "key": "sources"},
    {"label": "Delivery", "page": "pages/delivery.py", "key": "delivery"},
    {"label": "Editions", "page": "pages/history.py", "key": "history"},
]


def _format_date(d: date) -> str:
    """Format date cross-platform (avoids %-d which fails on Windows)."""
    return d.strftime(f"%A, %B {d.day}, %Y")


def render_header(current_page: str):
    """Render the compact header with title and inline navigation.

    Stacked minimal layout:
        PAPER BOY (centered, small)
        Home · Sources · Delivery · Editions (tab row)
        ─────────────────────────────────────── (thin rule)

    Args:
        current_page: Key of the active page ("dashboard", "sources", "delivery", "history").
    """
    # Title
    st.html(
        '<h1 class="compact-header-title">P A P E R &nbsp; B O Y</h1>'
    )

    # Navigation tabs
    cols = st.columns(len(NAV_ITEMS))
    for i, item in enumerate(NAV_ITEMS):
        is_active = item["key"] == current_page
        with cols[i]:
            if is_active:
                st.html(
                    f"""
                <div style="
                    text-align: center;
                    padding: 0.4rem 0;
                    font-family: 'Source Sans 3', sans-serif;
                    font-size: 0.8rem;
                    font-weight: 700;
                    letter-spacing: 0.04em;
                    text-transform: uppercase;
                    color: #1B1B1B;
                    border-bottom: 3px solid #C23B22;
                ">{item['label']}</div>
                """
                )
            else:
                if st.button(
                    item["label"],
                    key=f"nav_{item['key']}",
                    use_container_width=True,
                ):
                    st.switch_page(item["page"])

    st.html('<hr class="thin-rule" style="margin-bottom: 1rem;">')
