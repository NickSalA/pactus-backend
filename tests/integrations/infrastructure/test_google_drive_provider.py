"""Tests for Google Drive provider configuration."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from contractai_backend.modules.integrations.domain import InvalidCloudTokenError
from contractai_backend.modules.integrations.infrastructure.google_drive_provider import (
    GOOGLE_DRIVE_FILE_SCOPE,
    GoogleDriveProvider,
)


def _google_http_error(status: int) -> HttpError:
    return HttpError(SimpleNamespace(status=status, reason="Forbidden"), b'{"error": {"code": 403}}')


class TestGoogleDriveProvider:
    def test_uses_drive_file_scope(self):
        provider = GoogleDriveProvider(
            client_id="client-id",
            client_secret="client-secret",
            redirect_uri="https://example.com/integrations/drive/callback",
        )

        assert provider.scopes == [GOOGLE_DRIVE_FILE_SCOPE]

    @pytest.mark.asyncio
    async def test_metadata_access_for_unselected_drive_file_is_rejected(self):
        provider = GoogleDriveProvider(
            client_id="client-id",
            client_secret="client-secret",
            redirect_uri="https://example.com/integrations/drive/callback",
        )
        files_resource = MagicMock()
        files_resource.get.return_value.execute.side_effect = _google_http_error(403)
        drive_service = MagicMock()
        drive_service.files.return_value = files_resource

        with (
            patch("contractai_backend.modules.integrations.infrastructure.google_drive_provider.Credentials"),
            patch("contractai_backend.modules.integrations.infrastructure.google_drive_provider.build", return_value=drive_service),
        ):
            with pytest.raises(InvalidCloudTokenError):
                await provider.get_file_metadata({"token": "drive-token"}, "unselected-file-id")

        files_resource.get.assert_called_once_with(fileId="unselected-file-id", fields="id, name, mimeType, webViewLink")

    @pytest.mark.asyncio
    async def test_download_access_for_unselected_drive_file_is_rejected(self):
        provider = GoogleDriveProvider(
            client_id="client-id",
            client_secret="client-secret",
            redirect_uri="https://example.com/integrations/drive/callback",
        )
        files_resource = MagicMock()
        files_resource.get.return_value.execute.side_effect = _google_http_error(403)
        drive_service = MagicMock()
        drive_service.files.return_value = files_resource

        with (
            patch("contractai_backend.modules.integrations.infrastructure.google_drive_provider.Credentials"),
            patch("contractai_backend.modules.integrations.infrastructure.google_drive_provider.build", return_value=drive_service),
        ):
            with pytest.raises(InvalidCloudTokenError):
                await provider.download_file({"token": "drive-token"}, "unselected-file-id")

        files_resource.get.assert_called_once_with(fileId="unselected-file-id", fields="mimeType")
