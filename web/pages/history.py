"""Editions page — archive of built newspapers."""

import os
from datetime import date

import streamlit as st

from web.components.theme import inject_theme
from web.components.masthead import render_header
from web.components.cards import edition_card
from web.components.loading import show_empty_state
from web.services.database import get_delivery_history


inject_theme()
render_header("history")

history = get_delivery_history()

if not history:
    show_empty_state("no_history")
    st.stop()

# Display editions
for i, record in enumerate(history):
    edition_card(
        date_str=record.get("date", "Unknown date"),
        edition_number=record.get("edition_number", i + 1),
        article_count=record.get("article_count", 0),
        source_count=record.get("source_count", 0),
        file_size=record.get("file_size", "0 KB"),
        status=record.get("status", "unknown"),
        delivery_method=record.get("delivery_method", ""),
        error_message=record.get("error", ""),
    )

    # Action button — inline with each edition
    epub_path = record.get("epub_path", "")

    if record.get("status") == "delivered" and epub_path and os.path.exists(epub_path):
        with open(epub_path, "rb") as f:
            epub_bytes = f.read()
        edition_date = record.get("edition_date", date.today().isoformat())
        st.download_button(
            "Download EPUB",
            data=epub_bytes,
            file_name=f"paper-boy-{edition_date}.epub",
            mime="application/epub+zip",
            key=f"download_{i}",
            use_container_width=True,
        )
    elif record.get("status") == "failed":
        if st.button("Retry", key=f"retry_{i}", use_container_width=True):
            st.switch_page("pages/dashboard.py")

st.html(
    """
<div class="caption-text" style="text-align: center; margin-top: 1.5rem;">
    Showing the last 30 days of editions.
</div>
"""
)
