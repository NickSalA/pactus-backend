"""Tests unitarios para IntegrationService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contractai_backend.modules.integrations.application.services.integration_service import IntegrationService
from contractai_backend.modules.integrations.domain.exceptions import (
    CloudFileNotFoundError,
    CloudStorageIntegrationError,
    InvalidCloudTokenError,
    InvalidIntegrationPayloadError,
)


def _make_service(provider=None, ingestion=None) -> IntegrationService:
    return IntegrationService(
        provider=provider or AsyncMock(),
        ingestion_target=ingestion or AsyncMock(),
        index_name="contracts_index",
    )


class TestResolveContentType:
    def test_google_docs_returns_pdf(self):
        meta = {"mimeType": "application/vnd.google-apps.document"}
        result = IntegrationService._resolve_content_type(meta)
        assert result == "application/pdf"

    def test_regular_mime_returned_as_is(self):
        meta = {"mimeType": "application/pdf"}
        result = IntegrationService._resolve_content_type(meta)
        assert result == "application/pdf"

    def test_missing_mime_returns_octet_stream(self):
        result = IntegrationService._resolve_content_type({})
        assert result == "application/octet-stream"


class TestResolveFilename:
    def test_adds_pdf_extension_for_google_docs(self):
        meta = {"name": "mi_contrato", "mimeType": "application/vnd.google-apps.document"}
        result = IntegrationService._resolve_filename(meta, "file_id")
        assert result.endswith(".pdf")

    def test_keeps_existing_pdf_extension(self):
        meta = {"name": "contrato.pdf", "mimeType": "application/pdf"}
        result = IntegrationService._resolve_filename(meta, "file_id")
        assert result == "contrato.pdf"

    def test_uses_file_id_when_no_name(self):
        meta = {"mimeType": "application/pdf"}
        result = IntegrationService._resolve_filename(meta, "abc123")
        assert "abc123" in result


class TestGetAuthorizationUrl:
    def test_delegates_to_provider(self):
        provider = MagicMock()
        provider.get_auth_url.return_value = "https://auth.url"
        service = _make_service(provider=provider)
        url = service.get_authorization_url()
        assert url == "https://auth.url"


class TestProcessImport:
    @pytest.mark.asyncio
    async def test_completes_successfully(self):
        provider = AsyncMock()
        provider.get_file_metadata.return_value = {"name": "file.pdf", "mimeType": "application/pdf"}
        provider.download_file.return_value = b"pdf content"

        ingestion = AsyncMock()
        ingestion.ingest_drive_file.return_value = MagicMock(id=1)

        service = _make_service(provider=provider, ingestion=ingestion)
        files = [{"file_id": "abc", "document": {"name": "Test", "client": "Client"}}]

        result = await service.process_import(token={}, files=files, organization_id=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_raises_on_invalid_token(self):
        provider = AsyncMock()
        provider.get_file_metadata.side_effect = InvalidCloudTokenError()
        ingestion = AsyncMock()

        service = _make_service(provider=provider, ingestion=ingestion)
        files = [{"file_id": "unselected-file-id", "document": {}}]

        with pytest.raises(InvalidCloudTokenError):
            await service.process_import(token={}, files=files, organization_id=1)
        provider.get_file_metadata.assert_awaited_once_with({}, "unselected-file-id")

    @pytest.mark.asyncio
    async def test_raises_on_file_not_found(self):
        provider = AsyncMock()
        provider.get_file_metadata.side_effect = CloudFileNotFoundError()

        ingestion = AsyncMock()

        service = _make_service(provider=provider, ingestion=ingestion)
        files = [{"file_id": "missing", "document": {}}]

        with pytest.raises(CloudFileNotFoundError):
            await service.process_import(token={}, files=files, organization_id=1)

    @pytest.mark.asyncio
    async def test_raises_on_empty_file_id(self):
        provider = AsyncMock()
        ingestion = AsyncMock()

        service = _make_service(provider=provider, ingestion=ingestion)
        files = [{"file_id": "", "document": {}}]

        with pytest.raises(InvalidIntegrationPayloadError):
            await service.process_import(token={}, files=files, organization_id=1)
