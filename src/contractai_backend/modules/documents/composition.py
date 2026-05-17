"""Composition helpers for the documents module."""

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
    SQLModelDocumentRepository,
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
    structured_extractor: DocumentStructuredExtractor,
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
    )


def build_document_query_service(query_repo: DocumentQueryRepository) -> DocumentQueryService:
    """Builds the document query service from its query port."""
    return DocumentQueryService(sql_repo=query_repo)


def build_default_document_repository(session: AsyncSession) -> SQLModelDocumentRepository:
    """Builds the default SQL document repository without exposing infrastructure imports to other modules."""
    return SQLModelDocumentRepository(session=session)


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
    sql_repo = SQLModelDocumentRepository(session=session)
    return build_document_command_service(
        command_repo=sql_repo,
        query_repo=sql_repo,
        service_repo=SQLModelServiceRepository(session=session),
        folder_repo=SQLModelFolderRepository(session=session),
        vector_repo=LlamaIndexQdrantRepository(async_client=async_qdrant, sync_client=sync_qdrant),
        extractor=LlamaParseExtractor(),
        storage_repo=SupabaseStorageRepository(client=http_client),
        chunk_enricher=VectorChunkMetadataEnricher(),
        structured_extractor=GeminiDocumentStructuredExtractor(),
    )
