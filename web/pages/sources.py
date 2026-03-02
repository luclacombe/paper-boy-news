"""Sources page — manage RSS feeds and newsletters."""

import streamlit as st

from web.components.theme import inject_theme
from web.components.masthead import render_header
from web.components.cards import source_card
from web.components.loading import show_empty_state
from web.services.database import get_feeds, add_feed, remove_feed, get_user_config
from web.services.feed_catalog import (
    get_categories,
    get_bundles,
    get_feeds_for_bundle,
    validate_rss_url,
)


inject_theme()
render_header("sources")

# === TABS ===
tab_feeds, tab_newsletters = st.tabs(["RSS Feeds", "Newsletters"])


# ============================================================
# RSS FEEDS TAB
# ============================================================
with tab_feeds:
    feeds = get_feeds()

    # Build feed health from last build sections
    _sections = st.session_state.get("last_sections", [])
    _healthy_feeds = set()
    _feed_article_counts = {}
    for section in _sections:
        if section.articles:
            _healthy_feeds.add(section.name)
            _feed_article_counts[section.name] = len(section.articles)

    if not feeds:
        show_empty_state("no_sources")
    else:
        # List current feeds
        for feed in feeds:
            col1, col2 = st.columns([5, 1])
            with col1:
                feed_name = feed["name"]
                # Determine health: if we have build data, check results
                if _sections:
                    feed_status = "active" if feed_name in _healthy_feeds else "warning"
                else:
                    feed_status = "active"
                source_card(
                    name=feed_name,
                    url=feed["url"],
                    article_count=_feed_article_counts.get(feed_name),
                    status=feed_status,
                )
            with col2:
                # Vertically center the Remove button with CSS gap
                st.html('<div style="height: 0.75rem;"></div>')
                if st.button(
                    "Remove",
                    key=f"remove_{feed['url']}",
                    use_container_width=True,
                ):
                    remove_feed(feed["url"])
                    st.rerun()

    st.html("<hr class='thin-rule' style='margin: 1.5rem 0;'>")

    # === ADD A SOURCE ===
    st.html(
        """
    <div class="section-label" style="margin-bottom: 0.75rem;">
        ADD A SOURCE
    </div>
    """
    )

    # Browse feed library
    with st.expander("Browse feed library"):
        categories = get_categories()
        current_urls = {f["url"] for f in feeds}

        for category in categories:
            st.html(
                f'<div class="section-label" style="margin: 0.75rem 0 0.25rem 0;">'
                f"{category['name']}</div>"
            )
            for catalog_feed in category["feeds"]:
                already_added = catalog_feed["url"] in current_urls
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.html(
                        f"""
                    <div style="padding: 0.3rem 0;">
                        <span class="body-text" style="font-size: 0.9rem;">{catalog_feed['name']}</span>
                        <span class="caption-text" style="font-size: 0.8rem;"> &mdash; {catalog_feed['description']}</span>
                    </div>
                    """
                    )
                with col2:
                    if already_added:
                        st.button(
                            "\u2713 Added",
                            key=f"added_{catalog_feed['id']}",
                            disabled=True,
                            use_container_width=True,
                        )
                    else:
                        if st.button(
                            "Add",
                            key=f"add_{catalog_feed['id']}",
                            use_container_width=True,
                        ):
                            add_feed(
                                catalog_feed["name"],
                                catalog_feed["url"],
                                category["name"],
                            )
                            st.rerun()

    # Add custom RSS URL
    st.html(
        '<div class="body-text" style="margin: 0.75rem 0 0.5rem 0;">Or paste an RSS feed URL:</div>'
    )

    custom_col1, custom_col2 = st.columns([3, 1])
    with custom_col1:
        custom_url = st.text_input(
            "RSS URL",
            placeholder="https://example.com/feed/rss",
            label_visibility="collapsed",
            key="custom_rss_url",
        )
    with custom_col2:
        if st.button("Add Feed", use_container_width=True):
            if custom_url and validate_rss_url(custom_url):
                from urllib.parse import urlparse

                domain = urlparse(custom_url).netloc
                name = domain.replace("www.", "").split(".")[0].title()
                add_feed(name, custom_url, "Custom")
                st.rerun()
            elif custom_url:
                st.error("Please enter a valid RSS URL")

    # Quick add bundles
    st.html("<hr class='dotted-rule' style='margin: 1rem 0;'>")

    st.html(
        """
    <div class="section-label" style="margin-bottom: 0.5rem;">
        QUICK ADD BUNDLE
    </div>
    """
    )

    bundles = get_bundles()
    bundle_cols = st.columns(len(bundles))
    for i, bundle in enumerate(bundles):
        with bundle_cols[i]:
            if st.button(
                bundle["name"],
                key=f"src_bundle_{i}",
                use_container_width=True,
            ):
                bundle_feeds = get_feeds_for_bundle(bundle["name"])
                for bf in bundle_feeds:
                    add_feed(bf["name"], bf["url"], "Bundle")
                st.rerun()


# ============================================================
# NEWSLETTERS TAB
# ============================================================
with tab_newsletters:
    st.html(
        """
    <div style="text-align: center; padding: 3rem 1rem;">
        <div class="headline-text" style="font-size: 1.2rem; margin-bottom: 0.75rem;">
            Newsletter forwarding is coming soon
        </div>
        <div class="body-text" style="max-width: 500px; margin: 0 auto; font-size: 0.95rem; color: #7A7570;">
            Soon you'll be able to forward newsletters from your FT, NYT, Bloomberg,
            and WSJ subscriptions to a personal Paper Boy address. The newsletter
            content will be compiled into your morning paper automatically.
        </div>
        <div class="caption-text" style="margin-top: 1rem;">
            Newsletter content includes editorial commentary, analysis, and curated
            story summaries &mdash; not the full articles behind the paywall.
        </div>
    </div>
    """
    )
