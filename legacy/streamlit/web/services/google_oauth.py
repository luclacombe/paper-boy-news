"""Google OAuth2 flow for Drive and Gmail access."""

from __future__ import annotations

import logging
from typing import Optional

import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.send",
]


def _get_client_config() -> dict:
    """Build OAuth2 client config from Streamlit secrets."""
    return {
        "web": {
            "client_id": st.secrets["google"]["client_id"],
            "client_secret": st.secrets["google"]["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [st.secrets["google"]["redirect_uri"]],
        }
    }


def _get_redirect_uri() -> str:
    return st.secrets["google"]["redirect_uri"]


def is_configured() -> bool:
    """Check if Google OAuth secrets are present."""
    try:
        _ = st.secrets["google"]["client_id"]
        return True
    except (KeyError, FileNotFoundError):
        return False


def get_authorization_url() -> str:
    """Generate the Google OAuth2 authorization URL."""
    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=SCOPES,
        redirect_uri=_get_redirect_uri(),
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    st.session_state["oauth_state"] = state
    return auth_url


def handle_oauth_callback() -> Optional[dict]:
    """Check for OAuth callback params and exchange code for tokens.

    Returns token data dict on success, None if no callback present.
    Raises on exchange failure.
    """
    params = st.query_params
    code = params.get("code")
    if not code:
        return None

    try:
        flow = Flow.from_client_config(
            _get_client_config(),
            scopes=SCOPES,
            redirect_uri=_get_redirect_uri(),
            state=st.session_state.get("oauth_state"),
        )
        flow.fetch_token(code=code)
        creds = flow.credentials

        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes) if creds.scopes else list(SCOPES),
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
        }

        st.query_params.clear()
        logger.info("Google OAuth2 tokens obtained successfully")
        return token_data

    except Exception:
        st.query_params.clear()
        raise


def get_google_credentials(user_config: dict) -> Credentials:
    """Build valid Google credentials from stored token data.

    Refreshes the access token if expired and updates the config.
    """
    token_data = user_config.get("google_tokens")
    if not token_data or not token_data.get("refresh_token"):
        raise ValueError(
            "Google account not connected. "
            "Please connect your Google account in Delivery settings."
        )

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data["refresh_token"],
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data.get("scopes"),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_data["token"] = creds.token
        token_data["expiry"] = creds.expiry.isoformat() if creds.expiry else None
        logger.info("Google OAuth2 access token refreshed")

    return creds


def has_gmail_scope(user_config: dict) -> bool:
    """Check if stored tokens include the gmail.send scope."""
    token_data = user_config.get("google_tokens")
    if not token_data:
        return False
    scopes = token_data.get("scopes", [])
    return "https://www.googleapis.com/auth/gmail.send" in scopes


def has_drive_scope(user_config: dict) -> bool:
    """Check if stored tokens include the drive.file scope."""
    token_data = user_config.get("google_tokens")
    if not token_data:
        return False
    scopes = token_data.get("scopes", [])
    return "https://www.googleapis.com/auth/drive.file" in scopes
