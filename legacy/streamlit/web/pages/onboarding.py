"""Onboarding flow — 4-step setup wizard."""

import streamlit as st

from web.components.theme import inject_theme
from web.components.cards import device_card, bundle_card
from web.components.device_icons import (
    kindle_svg,
    kobo_svg,
    remarkable_svg,
    other_device_svg,
)
from web.services.feed_catalog import (
    get_bundles,
    get_categories,
    get_feeds_for_bundle,
    describe_feed_selection,
    validate_rss_url,
)
from web.services.database import save_user_config, complete_onboarding


inject_theme()

# Reading time -> article count mapping
READING_TIME_MAP = {
    "5 min": 3,
    "10 min": 5,
    "15 min": 8,
    "20 min": 10,
    "30 min": 15,
}

# Initialize onboarding state
if "onboarding_step" not in st.session_state:
    st.session_state["onboarding_step"] = 1
if "onboarding_feeds" not in st.session_state:
    st.session_state["onboarding_feeds"] = []
if "onboarding_device" not in st.session_state:
    st.session_state["onboarding_device"] = None
if "selected_bundles" not in st.session_state:
    st.session_state["selected_bundles"] = set()
if "show_individual_sources" not in st.session_state:
    st.session_state["show_individual_sources"] = False

current_step = st.session_state["onboarding_step"]


def _render_step_indicator(current: int, total: int = 4):
    """Render the step progress dots."""
    dots = ""
    for i in range(1, total + 1):
        if i < current:
            css_class = "step-dot step-dot-completed"
        elif i == current:
            css_class = "step-dot step-dot-active"
        else:
            css_class = "step-dot"
        dots += f'<span class="{css_class}"></span>'

    st.markdown(
        f"""
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;">
        <span class="caption-text">Step {current} of {total}</span>
        <div class="step-indicator">{dots}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def _render_page_title(title: str):
    """Render a consistent page title for each onboarding step."""
    st.markdown(
        f'<h2 class="masthead-title" style="font-size: 1.4rem; padding: 0.5rem 0; margin-bottom: 1rem;">'
        f"{title}</h2>",
        unsafe_allow_html=True,
    )


# ============================================================
# STEP 1: Choose Your Device
# ============================================================
if current_step == 1:
    _render_step_indicator(1)
    _render_page_title("What do you read on?")

    st.markdown(
        '<div class="body-text" style="text-align: center; margin-bottom: 1.5rem; color: #7A7570;">'
        "Choose your e-reader so we can set up delivery for you."
        "</div>",
        unsafe_allow_html=True,
    )

    devices = [
        ("Kindle", "kindle", kindle_svg()),
        ("Kobo", "kobo", kobo_svg()),
        ("reMarkable", "remarkable", remarkable_svg()),
        ("Other", "other", other_device_svg()),
    ]

    cols = st.columns(4)
    current_device = st.session_state.get("onboarding_device")

    for i, (name, key, svg) in enumerate(devices):
        with cols[i]:
            device_card(
                device_name=name,
                svg_icon=svg,
                selected=(current_device == key),
            )
            # Invisible button overlays the card (styled via CSS in theme.py)
            if st.button("\u200b", key=f"device_{key}", use_container_width=True):
                st.session_state["onboarding_device"] = key
                st.rerun()

    # Navigation: Continue only (no back on first step)
    left_spacer, center_col, right_spacer = st.columns([1, 1, 1])
    with center_col:
        if st.button(
            "Continue",
            type="primary",
            use_container_width=True,
            disabled=(current_device is None),
        ):
            st.session_state["onboarding_step"] = 2
            st.rerun()


# ============================================================
# STEP 2: How Do You Get Your News?
# ============================================================
elif current_step == 2:
    _render_step_indicator(2)
    _render_page_title("How do you get your news?")

    # Free Sources card (pre-selected since it's the only option)
    st.markdown(
        """
    <div class="pb-card pb-card-selected" style="padding: 1.5rem;">
        <div class="section-label" style="font-size: 0.85rem; margin-bottom: 0.75rem;">
            FREE SOURCES
        </div>
        <div class="headline-text" style="font-size: 1rem; margin-bottom: 0.5rem;">
            The world's best free journalism, curated into your morning paper.
        </div>
        <div class="body-text" style="font-size: 0.9rem; margin-bottom: 0.5rem;">
            Sources like The Guardian, NPR, Ars Technica, Reuters, and 25+ others.
            Full articles, not just headlines.
        </div>
        <div class="caption-text">Ready in 2 minutes.</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Paid Subscriptions card (coming soon)
    st.markdown(
        """
    <div class="pb-card" style="padding: 1.5rem; opacity: 0.6;">
        <div class="section-label" style="font-size: 0.85rem; margin-bottom: 0.75rem;">
            PAID SUBSCRIPTIONS
            <span class="badge badge-building" style="margin-left: 0.5rem;">Coming soon</span>
        </div>
        <div class="headline-text" style="font-size: 1rem; margin-bottom: 0.5rem;">
            Forward newsletters from your existing FT, NYT, Bloomberg, or WSJ subscription.
        </div>
        <div class="body-text" style="font-size: 0.9rem; margin-bottom: 0.5rem;">
            We compile the newsletter content &mdash; editorial commentary, analysis, and curated
            summaries &mdash; into your morning paper. These are digests, not full articles.
        </div>
        <div class="caption-text">Takes about 5 minutes to set up.</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="caption-text" style="text-align: center; margin-top: 1rem;">'
        "You can always add paid subscriptions later."
        "</div>",
        unsafe_allow_html=True,
    )

    # Consistent navigation: Back (left) / Continue (right)
    left_col, right_col = st.columns(2)
    with left_col:
        if st.button("Back", use_container_width=True):
            st.session_state["onboarding_step"] = 1
            st.rerun()
    with right_col:
        if st.button("Continue", type="primary", use_container_width=True):
            st.session_state["onboarding_path"] = "free"
            st.session_state["onboarding_step"] = 3
            st.rerun()


# ============================================================
# STEP 3: Pick Your Sources
# ============================================================
elif current_step == 3:
    _render_step_indicator(3)
    _render_page_title("Pick your sources")

    # === STARTER BUNDLES ===
    st.markdown(
        '<div class="section-label" style="margin-bottom: 0.75rem;">PICK YOUR BUNDLES</div>',
        unsafe_allow_html=True,
    )

    bundles = get_bundles()
    bundle_cols = st.columns(len(bundles))
    current_bundles = st.session_state.get("selected_bundles", set())

    for i, bundle in enumerate(bundles):
        with bundle_cols[i]:
            feeds_in_bundle = get_feeds_for_bundle(bundle["name"])
            feed_names = ", ".join(f["name"] for f in feeds_in_bundle[:4])
            if len(feeds_in_bundle) > 4:
                feed_names += f" +{len(feeds_in_bundle) - 4} more"

            is_selected = bundle["name"] in current_bundles
            bundle_card(
                name=bundle["name"],
                description=feed_names,
                selected=is_selected,
            )

            # Invisible button overlays the card (styled via CSS in theme.py)
            if st.button("\u200b", key=f"bundle_{i}", use_container_width=True):
                if is_selected:
                    # Deselect: remove bundle and its unique feeds
                    current_bundles.discard(bundle["name"])
                    # Collect URLs still covered by other selected bundles
                    still_covered_urls = set()
                    for other_name in current_bundles:
                        for f in get_feeds_for_bundle(other_name):
                            still_covered_urls.add(f["url"])
                    # Remove feeds unique to this bundle
                    for f in feeds_in_bundle:
                        if f["url"] not in still_covered_urls:
                            st.session_state[f"feed_{f['id']}"] = False
                            st.session_state["onboarding_feeds"] = [
                                of
                                for of in st.session_state["onboarding_feeds"]
                                if of["url"] != f["url"]
                            ]
                else:
                    # Select: add bundle and merge its feeds
                    current_bundles.add(bundle["name"])
                    existing_urls = {
                        f["url"] for f in st.session_state["onboarding_feeds"]
                    }
                    for f in feeds_in_bundle:
                        st.session_state[f"feed_{f['id']}"] = True
                        if f["url"] not in existing_urls:
                            st.session_state["onboarding_feeds"].append(
                                {
                                    "name": f["name"],
                                    "url": f["url"],
                                    "category": "Bundle",
                                }
                            )
                st.session_state["selected_bundles"] = current_bundles
                st.rerun()

    # === INDIVIDUAL SOURCES (collapsible) ===
    st.markdown('<hr class="thin-rule" style="margin: 1rem 0;">', unsafe_allow_html=True)

    # Track selected feed URLs
    selected_urls = {f["url"] for f in st.session_state["onboarding_feeds"]}
    categories = get_categories()

    show_label = (
        "Hide individual sources"
        if st.session_state["show_individual_sources"]
        else "Customize individual sources"
    )
    if st.button(show_label, use_container_width=True, key="toggle_sources"):
        new_show = not st.session_state["show_individual_sources"]
        st.session_state["show_individual_sources"] = new_show
        if new_show:
            # Force-sync checkbox keys from current feed selection when expanding
            for cat in categories:
                for feed in cat["feeds"]:
                    st.session_state[f"feed_{feed['id']}"] = (
                        feed["url"] in selected_urls
                    )
        st.rerun()

    if st.session_state["show_individual_sources"]:
        # Initialize any missing checkbox keys (first render after expand)
        for cat in categories:
            for feed in cat["feeds"]:
                cb_key = f"feed_{feed['id']}"
                if cb_key not in st.session_state:
                    st.session_state[cb_key] = feed["url"] in selected_urls

        # Display categories in 2-column layout
        cat_col1, cat_col2 = st.columns(2)

        for i, category in enumerate(categories):
            with cat_col1 if i % 2 == 0 else cat_col2:
                st.markdown(
                    f'<div class="section-label" style="margin-bottom: 0.5rem; margin-top: 0.75rem; font-size: 0.85rem;">'
                    f"{category['name']}</div>",
                    unsafe_allow_html=True,
                )

                for feed in category["feeds"]:
                    is_selected = feed["url"] in selected_urls
                    if st.checkbox(
                        feed["name"],
                        key=f"feed_{feed['id']}",
                        help=feed["description"],
                    ):
                        if not is_selected:
                            st.session_state["onboarding_feeds"].append(
                                {
                                    "name": feed["name"],
                                    "url": feed["url"],
                                    "category": category["name"],
                                }
                            )
                            selected_urls.add(feed["url"])
                    else:
                        if is_selected:
                            st.session_state["onboarding_feeds"] = [
                                f
                                for f in st.session_state["onboarding_feeds"]
                                if f["url"] != feed["url"]
                            ]
                            selected_urls.discard(feed["url"])

        # Full two-way sync: auto-select bundles whose feeds are all
        # checked, auto-deselect bundles missing any feed.
        synced_bundles = set()
        for bundle in bundles:
            bundle_feeds = get_feeds_for_bundle(bundle["name"])
            if all(f["url"] in selected_urls for f in bundle_feeds):
                synced_bundles.add(bundle["name"])
        if synced_bundles != st.session_state.get("selected_bundles", set()):
            st.session_state["selected_bundles"] = synced_bundles
            st.rerun()

        # === CUSTOM RSS URL ===
        st.markdown(
            '<hr class="thin-rule" style="margin: 1rem 0;">', unsafe_allow_html=True
        )
        st.markdown(
            '<div class="section-label" style="margin-bottom: 0.5rem;">ADD A CUSTOM RSS FEED</div>',
            unsafe_allow_html=True,
        )

        custom_col1, custom_col2 = st.columns([3, 1])
        with custom_col1:
            custom_url = st.text_input(
                "RSS URL",
                placeholder="https://example.com/rss",
                label_visibility="collapsed",
            )
        with custom_col2:
            if st.button("Add", use_container_width=True):
                if custom_url and validate_rss_url(custom_url):
                    from urllib.parse import urlparse

                    domain = urlparse(custom_url).netloc
                    name = domain.replace("www.", "").split(".")[0].title()
                    st.session_state["onboarding_feeds"].append(
                        {"name": name, "url": custom_url, "category": "Custom"}
                    )
                    st.rerun()
                elif custom_url:
                    st.error(
                        "Please enter a valid URL starting with http:// or https://"
                    )

    # === BOTTOM BAR ===
    feed_count = len(st.session_state["onboarding_feeds"])
    can_continue = feed_count >= 1

    feed_urls = {f["url"] for f in st.session_state["onboarding_feeds"]}
    selection_summary = describe_feed_selection(feed_urls)
    st.markdown(
        f'<div class="mono-text" style="text-align: center; padding: 0.5rem 0;">'
        f"{selection_summary} selected"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Consistent navigation: Back (left) / Continue (right)
    left_col, right_col = st.columns(2)
    with left_col:
        if st.button("Back", use_container_width=True, key="back_step3"):
            st.session_state["onboarding_step"] = 2
            st.rerun()
    with right_col:
        if st.button(
            "Continue",
            type="primary",
            use_container_width=True,
            disabled=not can_continue,
            key="next_step3",
        ):
            st.session_state["onboarding_step"] = 4
            st.rerun()


# ============================================================
# STEP 4: Delivery Setup
# ============================================================
elif current_step == 4:
    _render_step_indicator(4)
    _render_page_title("Set up your delivery")

    # Get device from step 1 (no need to ask again)
    device = st.session_state.get("onboarding_device", "other")

    device_display = {
        "kobo": "Kobo",
        "kindle": "Kindle",
        "remarkable": "reMarkable",
        "other": "Other",
    }

    st.markdown(
        f'<div class="body-text" style="text-align: center; margin-bottom: 1.5rem; color: #7A7570;">'
        f'Delivering to your <strong>{device_display.get(device, device)}</strong>.'
        f"</div>",
        unsafe_allow_html=True,
    )

    # Device-specific delivery options
    st.markdown(
        '<div class="section-label" style="margin-bottom: 0.75rem;">DELIVERY METHOD</div>',
        unsafe_allow_html=True,
    )

    kindle_email = ""

    if device == "kobo":
        delivery_method = st.radio(
            "Delivery method",
            options=["google_drive", "download"],
            format_func=lambda x: {
                "download": "Download Only",
                "google_drive": "Google Drive (auto-sync to Kobo)",
            }[x],
            index=0,
            label_visibility="collapsed",
        )
        if delivery_method == "google_drive":
            st.markdown(
                '<div class="pb-card" style="padding: 1.25rem;">'
                '<div class="body-text" style="font-size: 0.9rem; margin-bottom: 0.75rem;">'
                "Your newspaper appears in your Kobo library automatically via Google Drive sync.</div>"
                '<div class="caption-text">'
                "Requires Google Drive sync set up on your Kobo. "
                "Configure credentials in Delivery settings after setup.</div></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="pb-card" style="padding: 1.25rem;">'
                '<div class="body-text" style="font-size: 0.9rem;">'
                "Download each edition manually. No setup required &mdash; great for trying things out."
                "</div></div>",
                unsafe_allow_html=True,
            )

    elif device == "kindle":
        delivery_method = st.radio(
            "Delivery method",
            options=["email", "download"],
            format_func=lambda x: {
                "email": "Send to Kindle (via email)",
                "download": "Download Only",
            }[x],
            index=0,
            label_visibility="collapsed",
        )
        if delivery_method == "email":
            kindle_email = st.text_input(
                "Your Kindle email address",
                placeholder="your-name@kindle.com",
                help="Find this in your Kindle settings or Amazon account under 'Manage Your Content and Devices'.",
            )
            st.markdown(
                '<div class="pb-card" style="padding: 1.25rem;">'
                '<div class="body-text" style="font-size: 0.9rem;">'
                "We'll email each edition directly to your Kindle. "
                "Configure the sending email in Delivery settings after setup."
                "</div></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="pb-card" style="padding: 1.25rem;">'
                '<div class="body-text" style="font-size: 0.9rem;">'
                "Download and sideload via USB or email manually.</div></div>",
                unsafe_allow_html=True,
            )

    elif device == "remarkable":
        delivery_method = "download"
        st.markdown(
            '<div class="pb-card" style="padding: 1.25rem;">'
            '<div class="body-text" style="font-size: 0.9rem;">'
            "Download each edition and transfer to your reMarkable via USB "
            "or the reMarkable desktop app.</div></div>",
            unsafe_allow_html=True,
        )

    else:  # other
        delivery_method = "download"
        st.markdown(
            '<div class="pb-card" style="padding: 1.25rem;">'
            '<div class="body-text" style="font-size: 0.9rem;">'
            "Download each edition as an EPUB file. "
            "Works with any e-reader or reading app that supports EPUB.</div></div>",
            unsafe_allow_html=True,
        )

    # Delivery schedule
    st.markdown(
        '<div class="section-label" style="margin-top: 1rem; margin-bottom: 0.75rem;">DELIVERY SCHEDULE</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="body-text" style="font-size: 0.9rem; margin-bottom: 0.5rem;">'
        "Your paper will be ready every morning at:</div>",
        unsafe_allow_html=True,
    )

    time_col, tz_col = st.columns(2)
    with time_col:
        delivery_time = st.selectbox(
            "Time",
            options=["05:00", "05:30", "06:00", "06:30", "07:00", "07:30", "08:00"],
            index=2,  # Default 06:00
            format_func=lambda x: f"{x} AM" if x else x,
            label_visibility="collapsed",
        )
    with tz_col:
        timezone = st.selectbox(
            "Timezone",
            options=["UTC", "US/Eastern", "US/Central", "US/Pacific", "Europe/London", "Europe/Paris"],
            index=0,
            label_visibility="collapsed",
        )

    # Newspaper settings
    st.markdown(
        '<div class="section-label" style="margin-top: 1rem; margin-bottom: 0.75rem;">YOUR NEWSPAPER</div>',
        unsafe_allow_html=True,
    )

    title = st.text_input("Newspaper title", value="Morning Digest")

    # Time-based reading instead of technical article count
    st.markdown(
        '<div class="body-text" style="font-size: 0.9rem; margin: 0.5rem 0;">'
        "How long do you want to read each morning?</div>",
        unsafe_allow_html=True,
    )

    reading_time = st.select_slider(
        "Reading time",
        options=list(READING_TIME_MAP.keys()),
        value="20 min",
        label_visibility="collapsed",
    )
    max_articles = READING_TIME_MAP[reading_time]

    st.markdown(
        f'<div class="caption-text" style="margin-top: 0.25rem;">'
        f"Approximate &mdash; actual time depends on article length.</div>",
        unsafe_allow_html=True,
    )

    include_images = st.checkbox("Include images", value=True)

    # === FINISH BUTTON ===
    left_col, right_col = st.columns(2)
    with left_col:
        if st.button("Back", use_container_width=True, key="back_step4"):
            st.session_state["onboarding_step"] = 3
            st.rerun()
    with right_col:
        if st.button("Finish Setup", type="primary", use_container_width=True):
            # Save the config
            actual_method = delivery_method
            if actual_method == "download":
                actual_method = "local"

            config = {
                "title": title,
                "feeds": st.session_state["onboarding_feeds"],
                "device": device,
                "delivery_method": actual_method,
                "google_drive_folder": "Rakuten Kobo",
                "kindle_email": kindle_email if device == "kindle" else "",
                "email_smtp_host": "smtp.gmail.com",
                "email_smtp_port": 465,
                "email_sender": "",
                "email_password": "",
                "max_articles_per_feed": max_articles,
                "reading_time": reading_time,
                "include_images": include_images,
                "delivery_time": delivery_time,
                "language": "en",
            }
            save_user_config(config)
            complete_onboarding()

            # Clear onboarding state
            for key in [
                "onboarding_step",
                "onboarding_feeds",
                "onboarding_path",
                "started_onboarding",
                "onboarding_device",
                "selected_bundles",
                "show_individual_sources",
            ]:
                st.session_state.pop(key, None)

            st.rerun()
