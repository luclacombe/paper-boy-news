"""Landing page — the first thing a visitor sees."""

import streamlit as st

from web.components.theme import inject_theme


inject_theme()

# === HERO SECTION (compact) ===
st.markdown(
    """
<div style="text-align: center; padding: 1.5rem 0 0.75rem 0;">
    <hr class="thick-rule">
    <div style="padding: 1.25rem 0 0.75rem 0;">
        <h1 class="masthead-title" style="font-size: 2.5rem;">
            P A P E R &nbsp; B O Y
        </h1>
        <p class="masthead-subtitle" style="font-size: 1.15rem; margin-top: 0.5rem;">
            Your morning newspaper, assembled overnight,<br>
            delivered to your e-reader by dawn.
        </p>
    </div>
    <hr class="thin-rule">
</div>
""",
    unsafe_allow_html=True,
)

# === HOW IT WORKS — 3 COLUMNS ===
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
    <div class="how-it-works-card">
        <div class="how-it-works-number">1</div>
        <div class="how-it-works-title">Choose Sources</div>
        <div class="how-it-works-desc">
            Pick from free world-class sources, or forward your paid
            newsletter subscriptions.
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
    <div class="how-it-works-card">
        <div class="how-it-works-number">2</div>
        <div class="how-it-works-title">We Build It Overnight</div>
        <div class="how-it-works-desc">
            Your selections are compiled into a single
            newspaper-formatted EPUB, ready by morning.
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        """
    <div class="how-it-works-card">
        <div class="how-it-works-number">3</div>
        <div class="how-it-works-title">Read on Your E-Reader</div>
        <div class="how-it-works-desc">
            A beautiful edition waits on your e-reader every morning.
            No phone, no screen glare, just news.
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

# === CALL TO ACTION STATEMENT ===
st.markdown(
    """
<div style="text-align: center; padding: 1rem 0;">
    <div class="body-text" style="padding: 0.5rem 2rem; font-size: 1rem; color: #7A7570;">
        Your news, formatted for your e-reader, ready every morning.<br>
        Free. Open source. No ads. No tracking.
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# === GET STARTED BUTTON (at the bottom, after all info) ===
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("Get Started", type="primary", use_container_width=True):
        st.session_state["started_onboarding"] = True
        st.rerun()

    st.markdown(
        '<div style="text-align: center; margin-top: 0.25rem;">'
        '<span class="caption-text">No account required</span>'
        "</div>",
        unsafe_allow_html=True,
    )
