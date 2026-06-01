"""Dependency providers for the integrations module."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal
from uuid import uuid4

import httpx
from fastapi import Depends
from loguru import logger
from qdrant_client import AsyncQdrantClient, QdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.documents.application.services import DocumentCommandService
from contractai_backend.modules.documents.composition import build_default_document_command_service
from contractai_backend.modules.integrations.application import IntegrationService
from contractai_backend.modules.integrations.infrastructure import DocumentIngestionAdapter, GoogleDriveProvider
from contractai_backend.shared.config import settings
from contractai_backend.shared.infrastructure.database import get_aclient, get_client, get_session, get_session_context
from contractai_backend.shared.infrastructure.http import build_http_client, get_http_client

from .schemas import FilePhase, FileStatus, ImportEvent

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AsyncQdrantDep = Annotated[AsyncQdrantClient, Depends(get_aclient)]
SyncQdrantDep = Annotated[QdrantClient, Depends(get_client)]
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


def get_cloud_storage_provider() -> GoogleDriveProvider:
    """Builds the Google Drive integration provider."""
    return GoogleDriveProvider(
        client_id=settings.GOOGLE_CLIENT_ID, client_secret=settings.GOOGLE_CLIENT_SECRET, redirect_uri=settings.GOOGLE_REDIRECT_URI
    )


async def get_document_command_service(
    session: SessionDep,
    async_qdrant: AsyncQdrantDep,
    sync_qdrant: SyncQdrantDep,
    client: HttpClientDep,
) -> DocumentCommandService:
    """Builds the document service needed by Drive imports."""
    return build_default_document_command_service(session=session, async_qdrant=async_qdrant, sync_qdrant=sync_qdrant, http_client=client)


DocumentCommandServiceDep = Annotated[DocumentCommandService, Depends(get_document_command_service)]
CloudStorageProviderDep = Annotated[GoogleDriveProvider, Depends(get_cloud_storage_provider)]


def get_document_ingestion_target(
    document_service: DocumentCommandServiceDep,
) -> DocumentIngestionAdapter:
    """Builds the document ingestion target used by cloud imports."""
    return DocumentIngestionAdapter(document_service=document_service)


DocumentIngestionTargetDep = Annotated[DocumentIngestionAdapter, Depends(get_document_ingestion_target)]


def get_integration_service(
    provider: CloudStorageProviderDep,
    ingestion_target: DocumentIngestionTargetDep,
) -> IntegrationService:
    """Builds the application service for Google Drive integrations."""
    return IntegrationService(provider=provider, ingestion_target=ingestion_target, index_name=settings.DRIVE_INDEX_NAME)


@asynccontextmanager
async def build_background_integration_service() -> AsyncIterator[IntegrationService]:
    """Builds a task-scoped integration service for background imports."""
    provider = get_cloud_storage_provider()
    http_client = build_http_client()
    async_qdrant = None
    sync_qdrant = None

    try:
        async_qdrant = await get_aclient()
        sync_qdrant = get_client()

        async with get_session_context() as session:
            document_service = build_default_document_command_service(
                session=session,
                async_qdrant=async_qdrant,
                sync_qdrant=sync_qdrant,
                http_client=http_client,
            )
            ingestion_target = get_document_ingestion_target(document_service=document_service)

            yield get_integration_service(provider=provider, ingestion_target=ingestion_target)
    finally:
        if async_qdrant is not None:
            await async_qdrant.close()
        if sync_qdrant is not None:
            sync_qdrant.close()
        await http_client.aclose()


PING_TIMEOUT = 30


@dataclass
class JobTracker:
    job_id: str
    organization_id: int
    user_id: int
    status: Literal["RUNNING", "COMPLETED", "FAILED"] = "RUNNING"
    files: dict[str, FileStatus] = field(default_factory=dict)
    event_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    _cleanup_task: asyncio.Task | None = None

    async def set_phase(self, file_id: str, phase: FilePhase, error: str | None = None) -> None:
        file_status = self.files.get(file_id)
        if not file_status:
            return
        file_status.phase = phase
        file_status.error = error
        await self.event_queue.put(
            ImportEvent(
                type="file_update",
                job_id=self.job_id,
                status=self.status,
                files=list(self.files.values()),
            )
        )

    async def complete(self, status: Literal["COMPLETED", "FAILED"]) -> None:
        self.status = status
        await self.event_queue.put(
            ImportEvent(
                type="job_complete",
                job_id=self.job_id,
                status=status,
                files=list(self.files.values()),
            )
        )


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, JobTracker] = {}
        self._user_jobs: dict[int, str] = {}

    def create(self, files: list[dict[str, Any]], organization_id: int, user_id: int) -> JobTracker:
        job_id = str(uuid4())
        tracker = JobTracker(
            job_id=job_id,
            organization_id=organization_id,
            user_id=user_id,
            files={f["file_id"]: FileStatus(file_id=f["file_id"], phase=FilePhase.PENDING) for f in files},
        )
        self._jobs[job_id] = tracker
        self._user_jobs[user_id] = job_id
        return tracker

    def get(self, job_id: str) -> JobTracker | None:
        return self._jobs.get(job_id)

    def get_for_user(self, user_id: int) -> JobTracker | None:
        job_id = self._user_jobs.get(user_id)
        return self._jobs.get(job_id) if job_id else None

    async def schedule_cleanup(self, tracker: JobTracker) -> None:
        tracker._cleanup_task = asyncio.create_task(self._cleanup_after_delay(tracker.job_id))

    async def _cleanup_after_delay(self, job_id: str) -> None:
        await asyncio.sleep(900)
        self._jobs.pop(job_id, None)
        for uid, jid in list(self._user_jobs.items()):
            if jid == job_id:
                self._user_jobs.pop(uid, None)


job_registry = JobRegistry()


def create_job(files: list[dict[str, Any]], organization_id: int, user_id: int) -> JobTracker:
    return job_registry.create(files, organization_id, user_id)


def get_job(job_id: str) -> JobTracker | None:
    return job_registry.get(job_id)


def get_user_active_job(user_id: int) -> str | None:
    return job_registry._user_jobs.get(user_id)


def get_user_job_tracker(user_id: int) -> JobTracker | None:
    return job_registry.get_for_user(user_id)


async def update_file_phase(job_id: str, file_id: str, phase: FilePhase, error: str | None = None) -> None:
    tracker = job_registry.get(job_id)
    if not tracker:
        return
    await tracker.set_phase(file_id, phase, error)


async def complete_job(job_id: str, status: Literal["COMPLETED", "FAILED"]) -> None:
    tracker = job_registry.get(job_id)
    if not tracker:
        return
    await tracker.complete(status)
    await job_registry.schedule_cleanup(tracker)


async def _process_single_file(
    tracker: JobTracker,
    token: dict,
    file_item: dict[str, Any],
    organization_id: int,
    imported_by_user_id: int | None,
) -> bool:
    file_id = str(file_item.get("file_id") or "").strip()
    if not file_id:
        logger.warning("Skipping file with empty file_id")
        return True

    try:
        await tracker.set_phase(file_id, FilePhase.DATABASE)
    except Exception as e:
        logger.error(f"Error updating phase to DATABASE for file {file_id}: {e}")

    try:
        async with build_background_integration_service() as service:
            token_is_valid = await service.process_import(
                token=token,
                files=[file_item],
                organization_id=organization_id,
                imported_by_user_id=imported_by_user_id,
            )

        if not token_is_valid:
            await tracker.complete("FAILED")
            await job_registry.schedule_cleanup(tracker)
            return False

        await tracker.set_phase(file_id, FilePhase.KNOWLEDGE_BASE)
        await tracker.set_phase(file_id, FilePhase.COMPLETED)
        return True

    except Exception as e:
        logger.error(f"Error processing file {file_id}: {e}")
        try:
            await tracker.set_phase(file_id, FilePhase.FAILED, error="Error al procesar el archivo")
        except Exception as update_error:
            logger.error(f"Error updating phase to FAILED for file {file_id}: {update_error}")
        return True


async def process_drive_import_in_background(
    job_id: str,
    token: dict,
    files: list[dict[str, Any]],
    organization_id: int,
    imported_by_user_id: int | None = None,
) -> None:
    tracker = job_registry.get(job_id)
    if not tracker:
        logger.error(f"Job {job_id} not found in tracker")
        return

    for file_item in files:
        should_continue = await _process_single_file(
            tracker=tracker,
            token=token,
            file_item=file_item,
            organization_id=organization_id,
            imported_by_user_id=imported_by_user_id,
        )
        if not should_continue:
            return

    await tracker.complete("COMPLETED")
    await job_registry.schedule_cleanup(tracker)


async def generate_import_sse_events(tracker: JobTracker):
    initial_event = ImportEvent(
        type="initial_state",
        job_id=tracker.job_id,
        status=tracker.status,
        files=list(tracker.files.values()),
    )
    yield f"event: {initial_event.type}\ndata: {initial_event.model_dump_json(exclude={'type'})}\n\n"

    while True:
        try:
            event = await asyncio.wait_for(tracker.event_queue.get(), timeout=PING_TIMEOUT)
            yield f"event: {event.type}\ndata: {event.model_dump_json(exclude={'type'})}\n\n"
            if event.type == "job_complete":
                break
        except asyncio.TimeoutError:  # noqa: UP041
            yield "event: ping\ndata: null\n\n"
        except Exception as exc:
            logger.error(f"Error in SSE generator: {exc}")
            break

