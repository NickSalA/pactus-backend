"""Tests for Google Drive provider configuration."""

from urllib.parse import parse_qs, urlparse

from pactus_backend.modules.integrations.infrastructure.google_drive_provider import (
    GOOGLE_DRIVE_FILE_SCOPE,
    GoogleDriveProvider,
)


def _make_provider() -> GoogleDriveProvider:
    return GoogleDriveProvider(
        client_id="verified-client-id.apps.googleusercontent.com",
        client_secret="test-client-secret",
        redirect_uri="https://verified.example.com/integrations/drive/callback",
    )


def _parse_auth_url(provider: GoogleDriveProvider):
    parsed = urlparse(provider.get_auth_url())
    return parsed, parse_qs(parsed.query)


class TestGoogleDriveProvider:
    def test_uses_drive_file_scope(self):
        provider = _make_provider()

        assert provider.scopes == [GOOGLE_DRIVE_FILE_SCOPE]

    def test_auth_url_contains_google_oauth_endpoint(self):
        provider = _make_provider()

        parsed, _query = _parse_auth_url(provider)

        assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://accounts.google.com/o/oauth2/auth"

    def test_auth_url_contains_configured_client_id_and_redirect_uri(self):
        provider = _make_provider()

        _parsed, query = _parse_auth_url(provider)

        assert query["client_id"] == ["verified-client-id.apps.googleusercontent.com"]
        assert query["redirect_uri"] == ["https://verified.example.com/integrations/drive/callback"]

    def test_auth_url_does_not_include_client_secret(self):
        provider = _make_provider()

        parsed, query = _parse_auth_url(provider)
        auth_url = parsed.geturl()

        assert "client_secret" not in query
        assert "test-client-secret" not in auth_url

    def test_auth_url_contains_response_type_code(self):
        provider = _make_provider()

        _parsed, query = _parse_auth_url(provider)

        assert query["response_type"] == ["code"]

    def test_auth_url_requests_offline_access_consent_and_drive_file_scope_only(self):
        provider = _make_provider()

        _parsed, query = _parse_auth_url(provider)

        assert query["access_type"] == ["offline"]
        assert query["prompt"] == ["consent"]
        assert query["scope"] == [GOOGLE_DRIVE_FILE_SCOPE]
        assert "https://www.googleapis.com/auth/drive" not in query["scope"]
