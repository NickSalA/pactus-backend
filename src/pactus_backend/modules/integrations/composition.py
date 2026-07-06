"""Composition helpers for the integrations module."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from qdrant_client import AsyncQdrantClient, QdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ...modules.audit.composition import build_default_contract_activity_service
from ...modules.documents.composition import build_default_document_command_service
from ...shared.config import settings
from ...shared.infrastructure.database import get_aclient, get_client, get_session_context
from ...shared.infrastructure.http import build_http_client
from .application import IntegrationService
from .infrastructure import DocumentIngestionAdapter, GoogleDriveProvider


def build_cloud_storage_provider() -> GoogleDriveProvider:
    """Builds the Google Drive integration provider."""
    return GoogleDriveProvider(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )


def build_document_ingestion_target(
    session: AsyncSession,
    async_qdrant: AsyncQdrantClient,
    sync_qdrant: QdrantClient,
    http_client: httpx.AsyncClient,
) -> DocumentIngestionAdapter:
    """Builds the document ingestion target used by cloud imports."""
    document_service = build_default_document_command_service(
        session=session,
        async_qdrant=async_qdrant,
        sync_qdrant=sync_qdrant,
        http_client=http_client,
    )
    return DocumentIngestionAdapter(document_service=document_service)


def build_default_integration_service(
    session: AsyncSession,
    async_qdrant: AsyncQdrantClient,
    sync_qdrant: QdrantClient,
    http_client: httpx.AsyncClient,
) -> IntegrationService:
    """Builds the default integration service with all dependencies wired."""
    provider = build_cloud_storage_provider()
    ingestion_target = build_document_ingestion_target(
        session=session,
        async_qdrant=async_qdrant,
        sync_qdrant=sync_qdrant,
        http_client=http_client,
    )
    contract_activity_service = build_default_contract_activity_service(session=session)
    return IntegrationService(
        provider=provider,
        ingestion_target=ingestion_target,
        index_name=settings.DRIVE_INDEX_NAME,
        contract_activity_service=contract_activity_service,
    )


@asynccontextmanager
async def build_background_integration_service() -> AsyncIterator[IntegrationService]:
    """Builds a task-scoped integration service for background imports."""
    http_client = build_http_client()
    async_qdrant = None
    sync_qdrant = None

    try:
        async_qdrant = await get_aclient()
        sync_qdrant = get_client()

        async with get_session_context() as session:
            service = build_default_integration_service(
                session=session,
                async_qdrant=async_qdrant,
                sync_qdrant=sync_qdrant,
                http_client=http_client,
            )
            yield service
    finally:
        if async_qdrant is not None:
            await async_qdrant.close()
        if sync_qdrant is not None:
            sync_qdrant.close()
        await http_client.aclose()
