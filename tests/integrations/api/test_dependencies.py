"""Tests for task-scoped integration background dependencies."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contractai_backend.modules.integrations.api.dependencies import (
    build_background_integration_service,
    process_drive_import_in_background,
)


class _AsyncContextManager:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class TestBuildBackgroundIntegrationService:
    @pytest.mark.asyncio
    async def test_closes_task_scoped_resources_after_use(self):
        mock_provider = MagicMock()
        mock_http_client = AsyncMock()
        mock_async_qdrant = AsyncMock()
        mock_sync_qdrant = MagicMock()
        mock_session = MagicMock()
        mock_document_service = MagicMock()
        mock_ingestion_target = MagicMock()
        mock_integration_service = MagicMock()

        with (
            patch("contractai_backend.modules.integrations.api.dependencies.get_cloud_storage_provider", return_value=mock_provider),
            patch("contractai_backend.modules.integrations.api.dependencies.build_http_client", return_value=mock_http_client),
            patch(
                "contractai_backend.modules.integrations.api.dependencies.get_aclient",
                new=AsyncMock(return_value=mock_async_qdrant),
            ),
            patch("contractai_backend.modules.integrations.api.dependencies.get_client", return_value=mock_sync_qdrant),
            patch(
                "contractai_backend.modules.integrations.api.dependencies.get_session_context",
                return_value=_AsyncContextManager(mock_session),
            ),
            patch(
                "contractai_backend.modules.integrations.api.dependencies.build_default_document_command_service",
                return_value=mock_document_service,
            ) as mock_build_document_command_service,
            patch(
                "contractai_backend.modules.integrations.api.dependencies.get_document_ingestion_target",
                return_value=mock_ingestion_target,
            ) as mock_get_document_ingestion_target,
            patch(
                "contractai_backend.modules.integrations.api.dependencies.get_integration_service",
                return_value=mock_integration_service,
            ) as mock_get_integration_service,
        ):
            async with build_background_integration_service() as service:
                assert service is mock_integration_service

        mock_build_document_command_service.assert_called_once_with(
            session=mock_session,
            async_qdrant=mock_async_qdrant,
            sync_qdrant=mock_sync_qdrant,
            http_client=mock_http_client,
        )
        mock_get_document_ingestion_target.assert_called_once_with(document_service=mock_document_service)
        mock_get_integration_service.assert_called_once_with(provider=mock_provider, ingestion_target=mock_ingestion_target)
        mock_async_qdrant.close.assert_awaited_once()
        mock_sync_qdrant.close.assert_called_once_with()
        mock_http_client.aclose.assert_awaited_once()


class TestProcessDriveImportInBackground:
    @pytest.mark.asyncio
    async def test_process_import_uses_fresh_background_service_per_file(self):
        first_service = MagicMock()
        first_service.process_import = AsyncMock(return_value=True)
        second_service = MagicMock()
        second_service.process_import = AsyncMock(return_value=True)
        token = {"token": "abc"}
        first_file = {"file_id": "file-1", "document": {"name": "Contrato 1"}}
        second_file = {"file_id": "file-2", "document": {"name": "Contrato 2"}}
        files = [first_file, second_file]

        with patch(
            "contractai_backend.modules.integrations.api.dependencies.build_background_integration_service",
            side_effect=[_AsyncContextManager(first_service), _AsyncContextManager(second_service)],
        ) as mock_builder:
            await process_drive_import_in_background(token=token, files=files, organization_id=7, imported_by_user_id=3)

        assert mock_builder.call_count == 2
        first_service.process_import.assert_awaited_once_with(
            token=token,
            files=[first_file],
            organization_id=7,
            imported_by_user_id=3,
        )
        second_service.process_import.assert_awaited_once_with(
            token=token,
            files=[second_file],
            organization_id=7,
            imported_by_user_id=3,
        )

    @pytest.mark.asyncio
    async def test_process_import_stops_batch_when_token_becomes_invalid(self):
        first_service = MagicMock()
        first_service.process_import = AsyncMock(return_value=False)
        second_service = MagicMock()
        second_service.process_import = AsyncMock(return_value=True)
        token = {"token": "expired"}
        first_file = {"file_id": "file-1", "document": {"name": "Contrato 1"}}
        second_file = {"file_id": "file-2", "document": {"name": "Contrato 2"}}

        with patch(
            "contractai_backend.modules.integrations.api.dependencies.build_background_integration_service",
            side_effect=[_AsyncContextManager(first_service), _AsyncContextManager(second_service)],
        ) as mock_builder:
            await process_drive_import_in_background(
                token=token,
                files=[first_file, second_file],
                organization_id=7,
                imported_by_user_id=3,
            )

        assert mock_builder.call_count == 1
        first_service.process_import.assert_awaited_once_with(
            token=token,
            files=[first_file],
            organization_id=7,
            imported_by_user_id=3,
        )
        second_service.process_import.assert_not_called()
