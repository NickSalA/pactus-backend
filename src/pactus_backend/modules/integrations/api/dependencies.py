"""Dependency providers for the integrations module."""

from typing import Annotated

from fastapi import Depends
from httpx import AsyncClient
from qdrant_client import AsyncQdrantClient, QdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ....modules.documents.application.services import DocumentCommandService
from ....shared.infrastructure.database import get_aclient, get_client, get_session
from ....shared.infrastructure.http import get_http_client
from ..application import IntegrationService
from ..composition import (
    build_cloud_storage_provider,
    build_default_integration_service,
    build_document_ingestion_target,
)
from ..infrastructure import DocumentIngestionAdapter, GoogleDriveProvider


def get_cloud_storage_provider() -> GoogleDriveProvider:
    """Builds the Google Drive integration provider."""
    return build_cloud_storage_provider()


async def get_document_command_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    async_qdrant: Annotated[AsyncQdrantClient, Depends(get_aclient)],
    sync_qdrant: Annotated[QdrantClient, Depends(get_client)],
    client: Annotated[AsyncClient, Depends(get_http_client)],
) -> DocumentCommandService:
    """Builds the document service needed by Drive imports."""
    from ....modules.documents.composition import build_default_document_command_service  # noqa: PLC0415

    return build_default_document_command_service(
        session=session,
        async_qdrant=async_qdrant,
        sync_qdrant=sync_qdrant,
        http_client=client,
    )


DocumentCommandServiceDep = Annotated[DocumentCommandService, Depends(get_document_command_service)]
CloudStorageProviderDep = Annotated[GoogleDriveProvider, Depends(get_cloud_storage_provider)]


def get_document_ingestion_target(
    session: Annotated[AsyncSession, Depends(get_session)],
    async_qdrant: Annotated[AsyncQdrantClient, Depends(get_aclient)],
    sync_qdrant: Annotated[QdrantClient, Depends(get_client)],
    client: Annotated[AsyncClient, Depends(get_http_client)],
) -> DocumentIngestionAdapter:
    """Builds the document ingestion target used by cloud imports."""
    return build_document_ingestion_target(
        session=session,
        async_qdrant=async_qdrant,
        sync_qdrant=sync_qdrant,
        http_client=client,
    )


DocumentIngestionTargetDep = Annotated[DocumentIngestionAdapter, Depends(get_document_ingestion_target)]


def get_integration_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    async_qdrant: Annotated[AsyncQdrantClient, Depends(get_aclient)],
    sync_qdrant: Annotated[QdrantClient, Depends(get_client)],
    client: Annotated[AsyncClient, Depends(get_http_client)],
) -> IntegrationService:
    """Builds the application service for Google Drive integrations."""
    return build_default_integration_service(
        session=session,
        async_qdrant=async_qdrant,
        sync_qdrant=sync_qdrant,
        http_client=client,
    )
