"""Home — the main dashboard page."""

import os
import time
from datetime import date, datetime

import streamlit as st

from web.components.theme import inject_theme
from web.components.masthead import render_header
from web.components.cards import status_banner, headline_card
from web.components.loading import show_empty_state, BUILD_MESSAGES
from web.services.database import get_user_config, get_delivery_history, add_delivery_record
from web.services.builder import build_edition, deliver_edition
from web.services.feed_catalog import describe_feed_selection
from web.services import github_actions


def _format_time(dt: datetime) -> str:
    """Format time cross-platform (avoids %-I which fails on Windows)."""
    hour = dt.hour % 12 or 12
    am_pm = "AM" if dt.hour < 12 else "PM"
    return f"{hour}:{dt.strftime('%M')} {am_pm}"


def _format_date(dt) -> str:
    """Format date cross-platform (avoids %-d which fails on Windows)."""
    return dt.strftime(f"%A, %B {dt.day}, %Y")


def _delivery_needs_setup(config: dict) -> tuple[bool, str]:
    """Check if the user's delivery method needs additional setup.

    Returns (needs_setup, message) tuple.
    """
    method = config.get("delivery_method", "local")

    if method == "google_drive":
        # Check for OAuth2 tokens, env var, or credentials file
        has_oauth = (
            config.get("google_tokens")
            and config["google_tokens"].get("refresh_token")
        )
        has_service_account = (
            os.environ.get("GOOGLE_CREDENTIALS")
            or os.path.exists("credentials.json")
        )
        if not has_oauth and not has_service_account:
            return True, "Connect your Google account so editions are delivered to your Kobo automatically."
        return False, ""

    if method == "email":
        if not config.get("kindle_email"):
            return True, "Add your Kindle email address so editions can be sent to your Kindle."

        # Gmail API path — check for Google tokens with gmail.send scope
        email_method = config.get("email_method", "gmail")
        if email_method == "gmail":
            tokens = config.get("google_tokens")
            if tokens and "https://www.googleapis.com/auth/gmail.send" in tokens.get("scopes", []):
                return False, ""
            return True, "Connect your Google account to send editions to your Kindle via Gmail."

        # SMTP path — check for sender and password
        if not config.get("email_sender") or not config.get("email_password"):
            return True, "Add your SMTP email settings so editions are sent to your Kindle."
        return False, ""

    return False, ""


def _device_label(config: dict) -> str:
    """Human-readable device + delivery method label."""
    device = config.get("device", "other")
    method = config.get("delivery_method", "local")

    device_names = {
        "kobo": "Kobo",
        "kindle": "Kindle",
        "remarkable": "reMarkable",
        "other": "E-reader",
    }
    device_name = device_names.get(device, device)

    method_labels = {
        "google_drive": "via Google Drive",
        "email": "via email",
        "local": "download",
    }
    method_label = method_labels.get(method, method)

    return f"{device_name} \u00b7 {method_label}"


def _run_build(config: dict):
    """Execute the build + delivery pipeline with progress UI.

    Stores results in session_state and reruns the page on completion.
    """
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        for i, msg in enumerate(BUILD_MESSAGES[:3]):
            status_text.markdown(
                f'<div class="caption-text" style="text-align: center; font-style: italic;">'
                f"{msg}</div>",
                unsafe_allow_html=True,
            )
            progress_bar.progress([0.1, 0.3, 0.5][i])

        result = build_edition(config)
        epub_path = result.epub_path
        st.session_state["last_sections"] = result.sections

        status_text.markdown(
            f'<div class="caption-text" style="text-align: center; font-style: italic;">'
            f"{BUILD_MESSAGES[3]}</div>",
            unsafe_allow_html=True,
        )
        progress_bar.progress(0.7)

        # Deliver if not local-only
        delivery_method = config.get("delivery_method", "local")
        delivery_msg = ""
        if delivery_method != "local":
            status_text.markdown(
                f'<div class="caption-text" style="text-align: center; font-style: italic;">'
                f"{BUILD_MESSAGES[4]}</div>",
                unsafe_allow_html=True,
            )
            progress_bar.progress(0.85)
            delivery_ok, delivery_msg = deliver_edition(epub_path, config)
            if not delivery_ok:
                st.warning(f"Edition created but delivery failed: {delivery_msg}")

        # Get file size
        file_size_bytes = os.path.getsize(epub_path)
        if file_size_bytes > 1024 * 1024:
            file_size = f"{file_size_bytes / (1024 * 1024):.1f} MB"
        else:
            file_size = f"{file_size_bytes / 1024:.0f} KB"

        progress_bar.progress(1.0)
        status_text.empty()

        now = datetime.now()
        build_record = {
            "status": "delivered",
            "time": _format_time(now),
            "date": _format_date(now),
            "article_count": result.total_articles,
            "source_count": len([s for s in result.sections if s.articles]),
            "file_size": file_size,
            "file_size_bytes": file_size_bytes,
            "epub_path": str(epub_path),
            "edition_date": date.today().isoformat(),
            "delivery_method": delivery_method,
            "delivery_message": delivery_msg,
        }

        st.session_state["last_build"] = build_record
        st.session_state["last_epub_path"] = str(epub_path)

        edition_num = st.session_state.get("edition_number", 0) + 1
        st.session_state["edition_number"] = edition_num
        build_record["edition_number"] = edition_num

        add_delivery_record(build_record)
        time.sleep(1)
        st.rerun()

    except Exception as e:
        progress_bar.empty()
        status_text.empty()

        error_msg = str(e)
        if "No articles" in error_msg:
            friendly_msg = "None of your sources had new articles. This can happen on slow news days."
        elif "ConnectionError" in error_msg or "timeout" in error_msg.lower():
            friendly_msg = "We couldn't reach some of your sources. Please try again in a few minutes."
        else:
            friendly_msg = "Something went wrong while creating your edition. Please try again."

        st.session_state["last_build"] = {
            "status": "failed",
            "error": friendly_msg,
            "time": _format_time(datetime.now()),
        }
        st.rerun()


# === PAGE RENDER ===

inject_theme()
render_header("dashboard")

# Get user config
config = get_user_config()
feeds = config.get("feeds", [])

if not feeds:
    show_empty_state("no_sources")
    if st.button("Add Sources", type="primary"):
        st.switch_page("pages/sources.py")
    st.stop()


# === CHECK FOR FIRST-RUN EXPERIENCE ===
last_build = st.session_state.get("last_build")
_sections = st.session_state.get("last_sections", [])

if not last_build and not _sections:
    # First visit after onboarding — show setup summary
    _selection_desc = describe_feed_selection({f["url"] for f in feeds})
    _device_info = _device_label(config)
    _delivery_time = config.get("delivery_time", "06:00")
    _timezone = config.get("timezone", "UTC")

    needs_setup, setup_msg = _delivery_needs_setup(config)

    st.html(
        f"""
    <div class="pb-card" style="text-align: center; padding: 2rem 1.5rem;">
        <div class="headline-text" style="font-size: 1.3rem; margin-bottom: 1rem;">
            You're all set!
        </div>
        <div style="display: flex; flex-direction: column; gap: 0.4rem; align-items: center; margin-bottom: 1.25rem;">
            <div class="body-text" style="font-size: 0.95rem; color: #7A7570;">
                {_device_info}
            </div>
            <div class="body-text" style="font-size: 0.95rem; color: #7A7570;">
                {_selection_desc}
            </div>
            <div class="body-text" style="font-size: 0.95rem; color: #7A7570;">
                Daily at {_delivery_time} AM {_timezone}
            </div>
        </div>
    </div>
    """
    )

    if needs_setup:
        # Delivery method needs configuration — prompt setup
        st.html(
            f"""
        <div class="caption-text" style="text-align: center; margin: 0.75rem 0 0.5rem 0;">
            {setup_msg}
        </div>
        """
        )
        if st.button("Complete Delivery Setup", type="primary", use_container_width=True):
            st.switch_page("pages/delivery.py")

        st.html(
            '<div class="caption-text" style="text-align: center; margin-top: 0.75rem;">or</div>'
        )
        first_build_clicked = st.button(
            "Create First Edition (download only)",
            use_container_width=True,
        )
    else:
        # Setup is complete — create first edition
        delivery_method = config.get("delivery_method", "local")
        if delivery_method == "local":
            hint = "Your paper will be built daily. Download it here anytime."
        else:
            hint = f"After this, your paper will be built and delivered automatically each day at {_delivery_time} AM."

        st.html(
            f'<div class="caption-text" style="text-align: center; margin: 0.5rem 0;">{hint}</div>'
        )
        first_build_clicked = st.button(
            "Create My First Edition",
            type="primary",
            use_container_width=True,
        )

    st.html(
        '<div class="caption-text" style="text-align: center; margin-top: 0.5rem;">'
        "This usually takes 1-3 minutes.</div>"
    )

    if first_build_clicked:
        _run_build(config)

    st.stop()


# === DATE + EDITION LINE ===
_today = date.today()
_edition_num = st.session_state.get("edition_number")
_edition_text = f" &middot; Edition #{_edition_num}" if _edition_num else ""
st.html(
    f'<div class="masthead-date" style="margin-bottom: 0.75rem;">'
    f"{_format_date(_today)}{_edition_text}</div>"
)

# === STATUS BANNER ===
if last_build:
    if last_build["status"] == "delivered":
        status_banner(
            "delivered",
            f"Today's edition delivered at {last_build.get('time', '')}",
            f"{last_build.get('article_count', 0)} articles \u00b7 "
            f"{last_build.get('source_count', 0)} sources \u00b7 "
            f"{last_build.get('file_size', '')}",
        )
    elif last_build["status"] == "failed":
        status_banner(
            "failed",
            "Something went wrong while creating your edition.",
            last_build.get("error", "We'll try again automatically."),
        )
    elif last_build["status"] == "building":
        status_banner(
            "building",
            "Creating your edition...",
            "This usually takes 1-3 minutes.",
        )
else:
    status_banner(
        "empty",
        "No edition yet",
        "Click 'Create New Edition' to get started.",
    )

# === ACTION BUTTONS ===
btn_col1, btn_col2 = st.columns(2)

with btn_col1:
    epub_path = st.session_state.get("last_epub_path")
    if epub_path and os.path.exists(epub_path):
        with open(epub_path, "rb") as f:
            epub_bytes = f.read()
        today = date.today().isoformat()
        st.download_button(
            "Download EPUB",
            data=epub_bytes,
            file_name=f"paper-boy-{today}.epub",
            mime="application/epub+zip",
            use_container_width=True,
        )
    else:
        st.button("Download EPUB", disabled=True, use_container_width=True)

with btn_col2:
    build_clicked = st.button(
        "Create New Edition",
        type="primary",
        use_container_width=True,
    )

# GitHub Actions trigger (if configured)
if github_actions.is_configured():
    if st.button("Create on GitHub", use_container_width=True):
        if github_actions.trigger_build():
            st.success("Edition creation started on GitHub. Check Editions for status.")
        else:
            st.error("Failed to trigger GitHub Actions.")

# === BUILD PROCESS ===
if build_clicked:
    _run_build(config)


# === HEADLINES SECTION ===
st.html(
    '<div class="section-label" style="padding: 1rem 0 0.5rem 0; font-size: 0.8rem;">'
    "TODAY'S SOURCES</div>"
)

# Build headline mapping from last build's sections
_headlines_by_feed = {}
for section in _sections:
    _headlines_by_feed[section.name] = [a.title for a in section.articles]

# Display feeds in 2-column layout
col1, col2 = st.columns(2)

for i, feed in enumerate(feeds):
    with col1 if i % 2 == 0 else col2:
        feed_headlines = _headlines_by_feed.get(feed["name"], [])
        headline_card(
            source_name=feed["name"],
            headlines=feed_headlines,
            source_type=feed.get("type", "RSS"),
        )
