"""Paper Boy — Streamlit web app entry point."""

import os
import sys

import streamlit as st

# Ensure imports work for both `streamlit run web/app.py` from project root
# and `streamlit run app.py` from web/ directory
_web_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_web_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _web_dir not in sys.path:
    sys.path.insert(0, _web_dir)

# Add src/ to path for paper_boy imports
_src_dir = os.path.join(_project_root, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

st.set_page_config(
    page_title="Paper Boy",
    page_icon=":newspaper:",
    layout="centered",
    initial_sidebar_state="collapsed",
)

from web.services.database import is_onboarding_complete


def main():
    # Determine app state
    onboarding_done = is_onboarding_complete()

    if not onboarding_done:
        # Show landing or onboarding based on session state
        if st.session_state.get("started_onboarding"):
            pages = [
                st.Page("pages/onboarding.py", title="Setup", default=True),
            ]
        else:
            pages = [
                st.Page("pages/landing.py", title="Paper Boy", default=True),
            ]
    else:
        # Full app navigation
        pages = [
            st.Page("pages/dashboard.py", title="Home", default=True),
            st.Page("pages/sources.py", title="Sources"),
            st.Page("pages/delivery.py", title="Delivery"),
            st.Page("pages/history.py", title="Editions"),
        ]

    nav = st.navigation(pages, position="hidden")
    nav.run()


if __name__ == "__main__":
    main()
