from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends

from contractai_backend.modules.documents.api.dependencies import get_document_command_service
from contractai_backend.modules.documents.application.services import DocumentCommandService
from contractai_backend.modules.catalog.infrastructure.postgres_repo import SQLModelServiceRepository
from contractai_backend.modules.documents.infrastructure import (
    GeminiDocumentStructuredExtractor,
    LlamaIndexQdrantRepository,
    LlamaParseExtractor,
    SQLModelDocumentRepository,
    SupabaseStorageRepository,
    VectorChunkMetadataEnricher,
)
from contractai_backend.modules.folders.infrastructure.postgres_repo import SQLModelFolderRepository
from contractai_backend.modules.integrations.application import IntegrationService
from contractai_backend.modules.integrations.infrastructure import DocumentIngestionAdapter, GoogleDriveProvider
from contractai_backend.shared.config import settings
from contractai_backend.shared.infrastructure.database import get_aclient, get_client, get_session_context
from contractai_backend.shared.infrastructure.http import build_http_client


def get_cloud_storage_provider() -> GoogleDriveProvider:
    return GoogleDriveProvider(
        client_id=settings.GOOGLE_CLIENT_ID, client_secret=settings.GOOGLE_CLIENT_SECRET, redirect_uri=settings.GOOGLE_REDIRECT_URI
    )


def get_document_ingestion_target(
    document_service: DocumentCommandService = Depends(get_document_command_service),
) -> DocumentIngestionAdapter:
    return DocumentIngestionAdapter(document_service=document_service)


def get_integration_service(
    provider: GoogleDriveProvider = Depends(get_cloud_storage_provider),
    ingestion_target: DocumentIngestionAdapter = Depends(get_document_ingestion_target),
) -> IntegrationService:
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
            sql_repo = SQLModelDocumentRepository(session=session)
            service_repo = SQLModelServiceRepository(session=session)
            folder_repo = SQLModelFolderRepository(session=session)
            vector_repo = LlamaIndexQdrantRepository(async_client=async_qdrant, sync_client=sync_qdrant)
            extractor = LlamaParseExtractor()
            structured_extractor = GeminiDocumentStructuredExtractor()
            storage_repo = SupabaseStorageRepository(client=http_client)
            chunk_enricher = VectorChunkMetadataEnricher()

            document_service = await get_document_command_service(
                command_repo=sql_repo,
                query_repo=sql_repo,
                service_repo=service_repo,
                folder_repo=folder_repo,
                vector_repo=vector_repo,
                extractor=extractor,
                storage_repo=storage_repo,
                chunk_enricher=chunk_enricher,
                structured_extractor=structured_extractor,
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
