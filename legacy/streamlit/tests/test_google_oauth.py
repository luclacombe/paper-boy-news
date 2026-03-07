"""Tests for the Google OAuth2 flow service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# --- Helpers ---


def _make_query_params(code=None):
    """Build a MagicMock that behaves like st.query_params."""
    qp = MagicMock()
    qp.get = MagicMock(return_value=code)
    qp.clear = MagicMock()
    return qp


def _make_mock_creds(
    token="access-token",
    refresh_token="refresh-token",
    token_uri="https://oauth2.googleapis.com/token",
    client_id="test-id",
    client_secret="test-secret",
    scopes=None,
    expiry=None,
):
    """Build a MagicMock that behaves like google.oauth2.credentials.Credentials."""
    creds = MagicMock()
    creds.token = token
    creds.refresh_token = refresh_token
    creds.token_uri = token_uri
    creds.client_id = client_id
    creds.client_secret = client_secret
    creds.scopes = scopes if scopes is not None else {
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/gmail.send",
    }
    creds.expiry = expiry
    return creds


# --- Fixtures ---


@pytest.fixture
def valid_token_data():
    """A complete OAuth2 token data dict."""
    return {
        "token": "ya29.access-token-here",
        "refresh_token": "1//refresh-token-here",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test-client-id.apps.googleusercontent.com",
        "client_secret": "test-client-secret",
        "scopes": [
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/gmail.send",
        ],
        "expiry": "2026-03-02T12:00:00",
    }


@pytest.fixture
def drive_only_token_data():
    """Token data with only drive.file scope."""
    return {
        "token": "ya29.access-token",
        "refresh_token": "1//refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test-client-id.apps.googleusercontent.com",
        "client_secret": "test-client-secret",
        "scopes": ["https://www.googleapis.com/auth/drive.file"],
        "expiry": None,
    }


MOCK_SECRETS = {
    "google": {
        "client_id": "test-id",
        "client_secret": "test-secret",
        "redirect_uri": "http://localhost:8501",
    }
}


# --- TestIsConfigured ---


class TestIsConfigured:
    @patch("web.services.google_oauth.st")
    def test_returns_true_when_secrets_present(self, mock_st_mod):
        """Returns True when google secrets are configured."""
        mock_st_mod.secrets = {"google": {"client_id": "test-id"}}

        from web.services.google_oauth import is_configured

        assert is_configured() is True

    @patch("web.services.google_oauth.st")
    def test_returns_false_when_secrets_missing(self, mock_st_mod):
        """Returns False when google secrets are absent."""
        # Make secrets access raise KeyError
        mock_secrets = MagicMock()
        mock_secrets.__getitem__ = MagicMock(side_effect=KeyError("google"))
        mock_st_mod.secrets = mock_secrets

        from web.services.google_oauth import is_configured

        assert is_configured() is False

    @patch("web.services.google_oauth.st")
    def test_returns_false_when_secrets_file_missing(self, mock_st_mod):
        """Returns False when secrets.toml doesn't exist."""
        mock_secrets = MagicMock()
        mock_secrets.__getitem__ = MagicMock(
            side_effect=FileNotFoundError("No secrets file")
        )
        mock_st_mod.secrets = mock_secrets

        from web.services.google_oauth import is_configured

        assert is_configured() is False


# --- TestGetAuthorizationUrl ---


class TestGetAuthorizationUrl:
    @patch("web.services.google_oauth.Flow")
    @patch("web.services.google_oauth.st")
    def test_returns_url_string(self, mock_st_mod, mock_flow_cls):
        """Returns a URL string for Google OAuth consent."""
        mock_st_mod.secrets = MOCK_SECRETS
        mock_st_mod.session_state = {}

        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth?...",
            "random-state-token",
        )
        mock_flow_cls.from_client_config.return_value = mock_flow

        from web.services.google_oauth import get_authorization_url

        url = get_authorization_url()

        assert url.startswith("https://accounts.google.com")

    @patch("web.services.google_oauth.Flow")
    @patch("web.services.google_oauth.st")
    def test_stores_csrf_state_in_session(self, mock_st_mod, mock_flow_cls):
        """CSRF state is saved to session_state for validation."""
        mock_st_mod.secrets = MOCK_SECRETS
        mock_st_mod.session_state = {}

        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/...",
            "csrf-state-12345",
        )
        mock_flow_cls.from_client_config.return_value = mock_flow

        from web.services.google_oauth import get_authorization_url

        get_authorization_url()

        assert mock_st_mod.session_state["oauth_state"] == "csrf-state-12345"

    @patch("web.services.google_oauth.Flow")
    @patch("web.services.google_oauth.st")
    def test_requests_offline_access(self, mock_st_mod, mock_flow_cls):
        """Authorization URL requests offline access for refresh token."""
        mock_st_mod.secrets = MOCK_SECRETS
        mock_st_mod.session_state = {}

        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ("https://...", "state")
        mock_flow_cls.from_client_config.return_value = mock_flow

        from web.services.google_oauth import get_authorization_url

        get_authorization_url()

        call_kwargs = mock_flow.authorization_url.call_args[1]
        assert call_kwargs["access_type"] == "offline"
        assert call_kwargs["prompt"] == "consent"


# --- TestHandleOauthCallback ---


class TestHandleOauthCallback:
    @patch("web.services.google_oauth.st")
    def test_returns_none_when_no_code(self, mock_st_mod):
        """Returns None when no OAuth code in query params."""
        mock_st_mod.query_params = _make_query_params(code=None)

        from web.services.google_oauth import handle_oauth_callback

        result = handle_oauth_callback()
        assert result is None

    @patch("web.services.google_oauth.Flow")
    @patch("web.services.google_oauth.st")
    def test_exchanges_code_for_tokens(self, mock_st_mod, mock_flow_cls):
        """Exchanges authorization code for token data dict."""
        mock_st_mod.secrets = MOCK_SECRETS
        mock_st_mod.session_state = {"oauth_state": "saved-state"}
        mock_st_mod.query_params = _make_query_params(code="auth-code-from-google")

        mock_flow = MagicMock()
        mock_flow.credentials = _make_mock_creds()
        mock_flow_cls.from_client_config.return_value = mock_flow

        from web.services.google_oauth import handle_oauth_callback

        token_data = handle_oauth_callback()

        assert token_data is not None
        assert token_data["token"] == "access-token"
        assert token_data["refresh_token"] == "refresh-token"
        assert token_data["client_id"] == "test-id"
        mock_flow.fetch_token.assert_called_once_with(code="auth-code-from-google")

    @patch("web.services.google_oauth.Flow")
    @patch("web.services.google_oauth.st")
    def test_clears_query_params_after_exchange(self, mock_st_mod, mock_flow_cls):
        """Query params are cleared after successful code exchange."""
        mock_st_mod.secrets = MOCK_SECRETS
        mock_st_mod.session_state = {}
        mock_st_mod.query_params = _make_query_params(code="auth-code")

        mock_flow = MagicMock()
        mock_flow.credentials = _make_mock_creds()
        mock_flow_cls.from_client_config.return_value = mock_flow

        from web.services.google_oauth import handle_oauth_callback

        handle_oauth_callback()

        mock_st_mod.query_params.clear.assert_called_once()

    @patch("web.services.google_oauth.Flow")
    @patch("web.services.google_oauth.st")
    def test_clears_query_params_on_failure(self, mock_st_mod, mock_flow_cls):
        """Query params are cleared even if code exchange fails."""
        mock_st_mod.secrets = MOCK_SECRETS
        mock_st_mod.session_state = {}
        mock_st_mod.query_params = _make_query_params(code="bad-code")

        mock_flow = MagicMock()
        mock_flow.fetch_token.side_effect = Exception("Invalid grant")
        mock_flow_cls.from_client_config.return_value = mock_flow

        from web.services.google_oauth import handle_oauth_callback

        with pytest.raises(Exception, match="Invalid grant"):
            handle_oauth_callback()

        mock_st_mod.query_params.clear.assert_called_once()


# --- TestGetGoogleCredentials ---


class TestGetGoogleCredentials:
    def test_raises_when_no_tokens(self):
        """ValueError raised when google_tokens is absent."""
        from web.services.google_oauth import get_google_credentials

        with pytest.raises(ValueError, match="not connected"):
            get_google_credentials({})

    def test_raises_when_tokens_missing_refresh(self):
        """ValueError raised when refresh_token is None."""
        from web.services.google_oauth import get_google_credentials

        with pytest.raises(ValueError, match="not connected"):
            get_google_credentials({"google_tokens": {"token": "access-only"}})

    @patch("web.services.google_oauth.Request")
    @patch("web.services.google_oauth.Credentials")
    def test_builds_credentials_from_token_data(
        self, mock_creds_cls, mock_request_cls, valid_token_data
    ):
        """Credentials object is constructed from stored token data."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds_cls.return_value = mock_creds

        from web.services.google_oauth import get_google_credentials

        result = get_google_credentials({"google_tokens": valid_token_data})

        assert result is mock_creds
        mock_creds_cls.assert_called_once_with(
            token=valid_token_data["token"],
            refresh_token=valid_token_data["refresh_token"],
            token_uri=valid_token_data["token_uri"],
            client_id=valid_token_data["client_id"],
            client_secret=valid_token_data["client_secret"],
            scopes=valid_token_data["scopes"],
        )

    @patch("web.services.google_oauth.Request")
    @patch("web.services.google_oauth.Credentials")
    def test_refreshes_expired_token(self, mock_creds_cls, mock_request_cls, valid_token_data):
        """Expired credentials are refreshed automatically."""
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = "1//refresh"
        mock_creds.token = "new-access-token"
        mock_creds.expiry = MagicMock()
        mock_creds.expiry.isoformat.return_value = "2026-03-02T13:00:00"
        mock_creds_cls.return_value = mock_creds

        from web.services.google_oauth import get_google_credentials

        get_google_credentials({"google_tokens": valid_token_data})

        mock_creds.refresh.assert_called_once()
        assert valid_token_data["token"] == "new-access-token"
        assert valid_token_data["expiry"] == "2026-03-02T13:00:00"

    @patch("web.services.google_oauth.Request")
    @patch("web.services.google_oauth.Credentials")
    def test_does_not_refresh_valid_token(
        self, mock_creds_cls, mock_request_cls, valid_token_data
    ):
        """Non-expired credentials are not refreshed."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds_cls.return_value = mock_creds

        from web.services.google_oauth import get_google_credentials

        get_google_credentials({"google_tokens": valid_token_data})

        mock_creds.refresh.assert_not_called()


# --- TestScopeChecking ---


class TestScopeChecking:
    def test_has_gmail_scope_true(self, valid_token_data):
        """Returns True when gmail.send scope is present."""
        from web.services.google_oauth import has_gmail_scope

        assert has_gmail_scope({"google_tokens": valid_token_data}) is True

    def test_has_gmail_scope_false_when_missing(self, drive_only_token_data):
        """Returns False when gmail.send scope is absent."""
        from web.services.google_oauth import has_gmail_scope

        assert has_gmail_scope({"google_tokens": drive_only_token_data}) is False

    def test_has_gmail_scope_false_when_no_tokens(self):
        """Returns False when google_tokens is None."""
        from web.services.google_oauth import has_gmail_scope

        assert has_gmail_scope({}) is False
        assert has_gmail_scope({"google_tokens": None}) is False

    def test_has_drive_scope_true(self, valid_token_data):
        """Returns True when drive.file scope is present."""
        from web.services.google_oauth import has_drive_scope

        assert has_drive_scope({"google_tokens": valid_token_data}) is True

    def test_has_drive_scope_false_when_no_tokens(self):
        """Returns False when google_tokens is absent."""
        from web.services.google_oauth import has_drive_scope

        assert has_drive_scope({}) is False

    def test_has_drive_scope_false_empty_scopes(self):
        """Returns False when scopes list is empty."""
        from web.services.google_oauth import has_drive_scope

        tokens = {"scopes": []}
        assert has_drive_scope({"google_tokens": tokens}) is False


# --- TestTokenDataIntegrity ---


class TestTokenDataIntegrity:
    @patch("web.services.google_oauth.Flow")
    @patch("web.services.google_oauth.st")
    def test_token_data_contains_all_required_fields(self, mock_st_mod, mock_flow_cls):
        """Exchanged token data has all fields needed for credential reconstruction."""
        mock_st_mod.secrets = MOCK_SECRETS
        mock_st_mod.session_state = {}
        mock_st_mod.query_params = _make_query_params(code="code")

        mock_flow = MagicMock()
        mock_flow.credentials = _make_mock_creds()
        mock_flow_cls.from_client_config.return_value = mock_flow

        from web.services.google_oauth import handle_oauth_callback

        token_data = handle_oauth_callback()

        required_keys = {
            "token", "refresh_token", "token_uri",
            "client_id", "client_secret", "scopes", "expiry",
        }
        assert required_keys.issubset(set(token_data.keys()))

    @patch("web.services.google_oauth.Flow")
    @patch("web.services.google_oauth.st")
    def test_token_data_scopes_is_list_not_set(self, mock_st_mod, mock_flow_cls):
        """Scopes are serialized as a list (JSON-compatible), not a set."""
        mock_st_mod.secrets = MOCK_SECRETS
        mock_st_mod.session_state = {}
        mock_st_mod.query_params = _make_query_params(code="code")

        mock_flow = MagicMock()
        mock_flow.credentials = _make_mock_creds(scopes={"scope1", "scope2"})
        mock_flow_cls.from_client_config.return_value = mock_flow

        from web.services.google_oauth import handle_oauth_callback

        token_data = handle_oauth_callback()

        assert isinstance(token_data["scopes"], list)
