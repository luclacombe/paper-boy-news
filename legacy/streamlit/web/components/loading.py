"""Newspaper-themed loading states for Paper Boy."""

import time
import streamlit as st


# Newspaper production process messages
BUILD_MESSAGES = [
    "Setting the type...",
    "Pulling from the wire...",
    "Running the press...",
    "Folding and bundling...",
    "Out for delivery...",
]

# Empty state messages
EMPTY_STATES = {
    "no_sources": {
        "title": "Your newsstand is empty",
        "message": "Add some sources to get started.",
    },
    "no_editions": {
        "title": "No editions yet",
        "message": "Your first edition hasn't been created yet. Click 'Create New Edition' to get started.",
    },
    "no_newsletters": {
        "title": "No newsletters received",
        "message": "We haven't received any forwarded newsletters yet. It can take a few minutes for the first one to arrive.",
    },
    "no_history": {
        "title": "No editions yet",
        "message": "Your edition history will appear here after your first paper is created. Head to the Home page to create one.",
    },
}


def show_build_progress():
    """Show a newspaper-themed build progress indicator.

    Returns a placeholder that can be used to update status.
    """
    progress_bar = st.progress(0)
    status_text = st.empty()

    return progress_bar, status_text


def update_build_progress(
    progress_bar, status_text, step: int, total_steps: int = 5
):
    """Update the build progress with a newspaper-themed message.

    Args:
        progress_bar: Streamlit progress bar element.
        status_text: Streamlit empty element for status text.
        step: Current step (0-indexed).
        total_steps: Total number of steps.
    """
    progress = min((step + 1) / total_steps, 1.0)
    message = BUILD_MESSAGES[min(step, len(BUILD_MESSAGES) - 1)]

    progress_bar.progress(progress)
    status_text.markdown(
        f'<div class="caption-text" style="text-align: center; font-style: italic;">{message}</div>',
        unsafe_allow_html=True,
    )


def show_empty_state(state_key: str):
    """Show an empty state message.

    Args:
        state_key: One of "no_sources", "no_editions", "no_newsletters", "no_history".
    """
    state = EMPTY_STATES.get(state_key, EMPTY_STATES["no_editions"])

    st.html(
        f"""
    <div style="text-align: center; padding: 3rem 1rem;">
        <div class="headline-text" style="font-size: 1.2rem; margin-bottom: 0.5rem;">
            {state['title']}
        </div>
        <div class="caption-text" style="font-size: 1rem;">
            {state['message']}
        </div>
    </div>
    """
    )
