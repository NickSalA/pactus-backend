"""Tests unitarios para IntegrationService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contractai_backend.modules.integrations.application.services.integration_service import IntegrationService
from contractai_backend.modules.integrations.domain.exceptions import (
    CloudFileNotFoundError,
    CloudStorageIntegrationError,
    InvalidCloudTokenError,
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
    async def test_returns_true_on_success(self):
        provider = AsyncMock()
        provider.get_file_metadata.return_value = {"name": "file.pdf", "mimeType": "application/pdf"}
        provider.download_file.return_value = b"pdf content"

        ingestion = AsyncMock()
        ingestion.ingest_drive_file.return_value = MagicMock(id=1)

        service = _make_service(provider=provider, ingestion=ingestion)
        files = [{"file_id": "abc", "document": {"name": "Test", "client": "Client"}}]

        result = await service.process_import(token={}, files=files, organization_id=1)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_invalid_token(self):
        provider = AsyncMock()
        provider.get_file_metadata.side_effect = InvalidCloudTokenError()

        service = _make_service(provider=provider)
        files = [{"file_id": "abc", "document": {}}]

        result = await service.process_import(token={}, files=files, organization_id=1)
        assert result is False

    @pytest.mark.asyncio
    async def test_skips_file_not_found_and_continues(self):
        provider = AsyncMock()
        provider.get_file_metadata.side_effect = [
            CloudFileNotFoundError(),
            {"name": "file2.pdf", "mimeType": "application/pdf"},
        ]
        provider.download_file.return_value = b"content"

        ingestion = AsyncMock()
        ingestion.ingest_drive_file.return_value = MagicMock(id=2)

        service = _make_service(provider=provider, ingestion=ingestion)
        files = [
            {"file_id": "missing", "document": {}},
            {"file_id": "found", "document": {"name": "T", "client": "C"}},
        ]

        result = await service.process_import(token={}, files=files, organization_id=1)
        assert result is True
        ingestion.ingest_drive_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_file_id_skips_file(self):
        provider = AsyncMock()
        ingestion = AsyncMock()

        service = _make_service(provider=provider, ingestion=ingestion)
        files = [{"file_id": "", "document": {}}]

        result = await service.process_import(token={}, files=files, organization_id=1)
        assert result is True
        provider.get_file_metadata.assert_not_called()
