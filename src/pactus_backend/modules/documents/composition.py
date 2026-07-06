"""Composition helpers for the documents module."""

from typing import Any

import httpx
from qdrant_client import AsyncQdrantClient, QdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ..catalog.application.repositories import ServiceRepository
from ..catalog.infrastructure.postgres_repo import SQLModelServiceRepository
from ..folders.application.repositories import FolderRepository
from ..folders.infrastructure.postgres_repo import SQLModelFolderRepository
from .application.repositories import (
    DocumentChunkEnricher,
    DocumentCommandRepository,
    DocumentExtractor,
    DocumentQueryRepository,
    DocumentStorageRepository,
    DocumentStructuredExtractor,
    VectorRepository,
)
from .application.services import DocumentCommandService, DocumentQueryService
from .infrastructure import (
    GeminiDocumentStructuredExtractor,
    LlamaIndexQdrantRepository,
    LlamaParseExtractor,
    SQLModelDocumentCommandRepository,
    SQLModelDocumentQueryRepository,
    SupabaseStorageRepository,
    VectorChunkMetadataEnricher,
)


def build_document_command_service(
    *,
    command_repo: DocumentCommandRepository,
    query_repo: DocumentQueryRepository,
    service_repo: ServiceRepository,
    folder_repo: FolderRepository,
    vector_repo: VectorRepository,
    extractor: DocumentExtractor,
    storage_repo: DocumentStorageRepository,
    chunk_enricher: DocumentChunkEnricher,
    structured_extractor: DocumentStructuredExtractor | None = None,
    ai_token_tracking_service: Any | None = None,
) -> DocumentCommandService:
    """Builds the document command service from module ports."""
    return DocumentCommandService(
        command_repo=command_repo,
        query_repo=query_repo,
        service_repo=service_repo,
        vector_repo=vector_repo,
        extractor=extractor,
        storage_repo=storage_repo,
        chunk_enricher=chunk_enricher,
        folder_repo=folder_repo,
        structured_extractor=structured_extractor,
        ai_token_tracking_service=ai_token_tracking_service,
    )


def build_document_query_service(query_repo: DocumentQueryRepository) -> DocumentQueryService:
    """Builds the document query service from its query port."""
    return DocumentQueryService(sql_repo=query_repo)


def build_default_document_repository(session: AsyncSession) -> SQLModelDocumentQueryRepository:
    """Builds the default SQL document query repository without exposing infrastructure imports to other modules."""
    return SQLModelDocumentQueryRepository(session=session)


def build_default_document_extractor() -> DocumentExtractor:
    """Builds the default document text extractor."""
    return LlamaParseExtractor()


def build_default_document_command_service(
    *,
    session: AsyncSession,
    async_qdrant: AsyncQdrantClient,
    sync_qdrant: QdrantClient,
    http_client: httpx.AsyncClient,
) -> DocumentCommandService:
    """Builds the default production document command service graph."""
    from ..audit.composition import build_default_ai_token_tracking_service  # noqa: PLC0415

    return build_document_command_service(
        command_repo=SQLModelDocumentCommandRepository(session=session),
        query_repo=SQLModelDocumentQueryRepository(session=session),
        service_repo=SQLModelServiceRepository(session=session),
        folder_repo=SQLModelFolderRepository(session=session),
        vector_repo=LlamaIndexQdrantRepository(async_client=async_qdrant, sync_client=sync_qdrant),
        extractor=LlamaParseExtractor(),
        storage_repo=SupabaseStorageRepository(client=http_client),
        chunk_enricher=VectorChunkMetadataEnricher(),
        structured_extractor=GeminiDocumentStructuredExtractor(),
        ai_token_tracking_service=build_default_ai_token_tracking_service(session=session),
    )
