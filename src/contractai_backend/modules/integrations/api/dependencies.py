"""Dependency providers for the integrations module."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx
from fastapi import Depends
from qdrant_client import AsyncQdrantClient, QdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.documents.application.services import DocumentCommandService
from contractai_backend.modules.documents.composition import build_default_document_command_service
from contractai_backend.modules.integrations.application import IntegrationService
from contractai_backend.modules.integrations.infrastructure import DocumentIngestionAdapter, GoogleDriveProvider
from contractai_backend.shared.config import settings
from contractai_backend.shared.infrastructure.database import get_aclient, get_client, get_session, get_session_context
from contractai_backend.shared.infrastructure.http import build_http_client, get_http_client

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


async def process_drive_import_in_background(
    token: dict,
    files: list[dict[str, Any]],
    organization_id: int,
    imported_by_user_id: int | None = None,
) -> None:
    """Executes a Drive import with fresh task-scoped dependencies."""
    for file_item in files:
        async with build_background_integration_service() as service:
            token_is_valid = await service.process_import(
                token=token,
                files=[file_item],
                organization_id=organization_id,
                imported_by_user_id=imported_by_user_id,
            )

        if not token_is_valid:
            break
