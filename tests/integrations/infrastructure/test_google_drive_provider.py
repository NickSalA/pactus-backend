"""Tests for Google Drive provider configuration."""

from contractai_backend.modules.integrations.infrastructure.google_drive_provider import (
    GOOGLE_DRIVE_FILE_SCOPE,
    GoogleDriveProvider,
)


class TestGoogleDriveProvider:
    def test_uses_drive_file_scope(self):
        provider = GoogleDriveProvider(
            client_id="client-id",
            client_secret="client-secret",
            redirect_uri="https://example.com/integrations/drive/callback",
        )

        assert provider.scopes == [GOOGLE_DRIVE_FILE_SCOPE]
