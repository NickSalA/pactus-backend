"""Tests for task-scoped integration background dependencies."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pactus_backend.modules.integrations.composition import (
    build_background_integration_service,
)
from pactus_backend.modules.integrations.application.jobs import (
    create_job,
    job_registry,
    FilePhase,
)
from pactus_backend.modules.integrations.application.services.job_orchestrator import (
    process_drive_import_in_background,
)
from pactus_backend.modules.integrations.domain.exceptions import InvalidCloudTokenError


class _AsyncContextManager:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def clear_job_registry():
    job_registry._jobs.clear()
    job_registry._user_jobs.clear()
    yield
    job_registry._jobs.clear()
    job_registry._user_jobs.clear()


class TestBuildBackgroundIntegrationService:
    @pytest.mark.asyncio
    async def test_closes_task_scoped_resources_after_use(self):
        mock_provider = MagicMock()
        mock_http_client = AsyncMock()
        mock_async_qdrant = AsyncMock()
        mock_sync_qdrant = MagicMock()
        mock_session = MagicMock()
        mock_ingestion_target = MagicMock()
        mock_contract_activity_service = MagicMock()

        with (
            patch("pactus_backend.modules.integrations.composition.build_cloud_storage_provider", return_value=mock_provider),
            patch("pactus_backend.modules.integrations.composition.build_http_client", return_value=mock_http_client),
            patch(
                "pactus_backend.modules.integrations.composition.get_aclient",
                new=AsyncMock(return_value=mock_async_qdrant),
            ),
            patch("pactus_backend.modules.integrations.composition.get_client", return_value=mock_sync_qdrant),
            patch(
                "pactus_backend.modules.integrations.composition.get_session_context",
                return_value=_AsyncContextManager(mock_session),
            ),
            patch(
                "pactus_backend.modules.integrations.composition.build_document_ingestion_target",
                return_value=mock_ingestion_target,
            ) as mock_get_document_ingestion_target,
            patch(
                "pactus_backend.modules.integrations.composition.build_default_contract_activity_service",
                return_value=mock_contract_activity_service,
            ) as mock_build_contract_activity_service,
        ):
            async with build_background_integration_service() as service:
                assert service.provider is mock_provider
                assert service.ingestion_target is mock_ingestion_target
                assert service.contract_activity_service is mock_contract_activity_service

        mock_get_document_ingestion_target.assert_called_once_with(
            session=mock_session,
            async_qdrant=mock_async_qdrant,
            sync_qdrant=mock_sync_qdrant,
            http_client=mock_http_client,
        )
        mock_build_contract_activity_service.assert_called_once_with(session=mock_session)
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
        tracker = create_job(files=files, organization_id=7, user_id=3)

        with (
            patch(
                "pactus_backend.modules.integrations.application.services.job_orchestrator.build_background_integration_service",
                side_effect=[_AsyncContextManager(first_service), _AsyncContextManager(second_service)],
            ) as mock_builder,
            patch.object(job_registry, "schedule_cleanup", new=AsyncMock()) as mock_schedule_cleanup,
            patch.object(tracker, "set_phase", wraps=tracker.set_phase) as mock_set_phase,
        ):
            await process_drive_import_in_background(
                tracker.job_id,
                token=token,
                files=files,
                organization_id=7,
                imported_by_user_id=3,
            )

        assert mock_builder.call_count == 2
        mock_schedule_cleanup.assert_awaited_once_with(tracker)
        assert tracker.status == "COMPLETED"
        assert [call.args for call in mock_set_phase.await_args_list] == [
            ("file-1", FilePhase.DATABASE),
            ("file-1", FilePhase.KNOWLEDGE_BASE),
            ("file-1", FilePhase.COMPLETED),
            ("file-2", FilePhase.DATABASE),
            ("file-2", FilePhase.KNOWLEDGE_BASE),
            ("file-2", FilePhase.COMPLETED),
        ]
        queued_events = []
        while not tracker.event_queue.empty():
            queued_events.append(tracker.event_queue.get_nowait())
        assert queued_events[-1].type == "job_complete"
        assert queued_events[-1].status == "COMPLETED"
        first_service.process_import.assert_awaited_once_with(
            token=token,
            files=[first_file],
            organization_id=7,
            imported_by_user_id=3,
            imported_by=None,
        )
        second_service.process_import.assert_awaited_once_with(
            token=token,
            files=[second_file],
            organization_id=7,
            imported_by_user_id=3,
            imported_by=None,
        )

    @pytest.mark.asyncio
    async def test_process_import_stops_batch_when_token_becomes_invalid(self):
        first_service = MagicMock()
        first_service.process_import = AsyncMock(side_effect=InvalidCloudTokenError())
        second_service = MagicMock()
        second_service.process_import = AsyncMock(return_value=None)
        token = {"token": "expired"}
        first_file = {"file_id": "file-1", "document": {"name": "Contrato 1"}}
        second_file = {"file_id": "file-2", "document": {"name": "Contrato 2"}}
        files = [first_file, second_file]
        tracker = create_job(files=files, organization_id=7, user_id=3)

        with (
            patch(
                "pactus_backend.modules.integrations.application.services.job_orchestrator.build_background_integration_service",
                side_effect=[_AsyncContextManager(first_service), _AsyncContextManager(second_service)],
            ) as mock_builder,
            patch.object(job_registry, "schedule_cleanup", new=AsyncMock()) as mock_schedule_cleanup,
        ):
            await process_drive_import_in_background(
                tracker.job_id,
                token=token,
                files=files,
                organization_id=7,
                imported_by_user_id=3,
            )

        assert mock_builder.call_count == 1
        mock_schedule_cleanup.assert_awaited_once_with(tracker)
        assert tracker.status == "FAILED"
        first_service.process_import.assert_awaited_once_with(
            token=token,
            files=[first_file],
            organization_id=7,
            imported_by_user_id=3,
            imported_by=None,
        )
        second_service.process_import.assert_not_called()

    @pytest.mark.asyncio
    async def test_marks_file_as_failed_when_service_raises(self):
        service = MagicMock()
        service.process_import = AsyncMock(side_effect=Exception("Internal error"))
        token = {"token": "abc"}
        first_file = {"file_id": "file-1", "document": {"name": "Contrato"}}
        files = [first_file]
        tracker = create_job(files=files, organization_id=7, user_id=3)

        with (
            patch(
                "pactus_backend.modules.integrations.application.services.job_orchestrator.build_background_integration_service",
                side_effect=[_AsyncContextManager(service)],
            ) as mock_builder,
            patch.object(job_registry, "schedule_cleanup", new=AsyncMock()) as mock_schedule_cleanup,
        ):
            await process_drive_import_in_background(
                tracker.job_id,
                token=token,
                files=files,
                organization_id=7,
                imported_by_user_id=3,
            )

        assert mock_builder.call_count == 1
        mock_schedule_cleanup.assert_awaited_once_with(tracker)
        assert tracker.files["file-1"].phase == FilePhase.FAILED
        assert tracker.files["file-1"].error == "Error al procesar el archivo"

    @pytest.mark.asyncio
    async def test_logs_processing_error_when_file_fails(self):
        service = MagicMock()
        service.process_import = AsyncMock(side_effect=Exception("vectorization failed"))
        token = {"token": "abc"}
        file_item = {"file_id": "file-1", "document": {"name": "Contrato"}}
        tracker = create_job(files=[file_item], organization_id=7, user_id=3)

        with (
            patch(
                "pactus_backend.modules.integrations.application.services.job_orchestrator.build_background_integration_service",
                side_effect=[_AsyncContextManager(service)],
            ),
            patch.object(job_registry, "schedule_cleanup", new=AsyncMock()),
            patch("pactus_backend.modules.integrations.application.services.job_orchestrator.logger.error") as mock_logger_error,
        ):
            await process_drive_import_in_background(
                tracker.job_id,
                token=token,
                files=[file_item],
                organization_id=7,
                imported_by_user_id=3,
            )

        mock_logger_error.assert_called_once()
        assert "Error processing file file-1" in mock_logger_error.call_args.args[0]
        assert "vectorization failed" in mock_logger_error.call_args.args[0]
