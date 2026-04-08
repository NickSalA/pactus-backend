"""Dependency Injection for the documents module."""

from typing import Annotated

import httpx
from fastapi import Depends
from qdrant_client import AsyncQdrantClient, QdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ....shared.infrastructure.database import get_aclient, get_client, get_session
from ....shared.infrastructure.http import get_http_client
from ..application.repositories import (
    DocumentChunkEnricher,
    DocumentCommandRepository,
    DocumentExtractor,
    DocumentQueryRepository,
    DocumentStorageRepository,
    VectorRepository,
)
from ..application.services import DocumentCommandService, DocumentQueryService
from ..infrastructure import (
    LlamaIndexQdrantRepository,
    LlamaParseExtractor,
    SQLModelDocumentRepository,
    SupabaseStorageRepository,
    VectorChunkMetadataEnricher,
)
from ...catalog.api.dependencies import get_service_repository
from ...catalog.application.repositories import ServiceRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AsyncQdrantDep = Annotated[AsyncQdrantClient, Depends(get_aclient)]
SyncQdrantDep = Annotated[QdrantClient, Depends(get_client)]


async def get_document_relational_repository(session: SessionDep) -> SQLModelDocumentRepository:
    """Construye el repositorio SQL de documentos."""
    return SQLModelDocumentRepository(session=session)


async def get_document_query_repository(
    repo: Annotated[SQLModelDocumentRepository, Depends(get_document_relational_repository)],
) -> DocumentQueryRepository:
    """Exposes the SQL repo through the query port."""
    return repo


async def get_document_command_repository(
    repo: Annotated[SQLModelDocumentRepository, Depends(get_document_relational_repository)],
) -> DocumentCommandRepository:
    """Exposes the SQL repo through the command port."""
    return repo


async def get_vector_repository(async_qdrant: AsyncQdrantDep, sync_qdrant: SyncQdrantDep) -> VectorRepository:
    """Construye un repositorio de vectores Qdrant."""
    return LlamaIndexQdrantRepository(async_client=async_qdrant, sync_client=sync_qdrant)


async def get_extractor() -> DocumentExtractor:
    """Construye un extractor de datos basado en LlamaParse."""
    return LlamaParseExtractor()


async def get_storage_repository(client: Annotated[httpx.AsyncClient, Depends(get_http_client)]) -> DocumentStorageRepository:
    """Construye un repositorio de almacenamiento Supabase."""
    return SupabaseStorageRepository(client=client)


async def get_chunk_enricher() -> DocumentChunkEnricher:
    """Construye el enriquecedor de metadata para chunks vectoriales."""
    return VectorChunkMetadataEnricher()


DocumentQueryRepoDep = Annotated[DocumentQueryRepository, Depends(get_document_query_repository)]
DocumentCommandRepoDep = Annotated[DocumentCommandRepository, Depends(get_document_command_repository)]
ServiceRepoDep = Annotated[ServiceRepository, Depends(get_service_repository)]
VectorRepoDep = Annotated[VectorRepository, Depends(get_vector_repository)]
ExtractorDep = Annotated[DocumentExtractor, Depends(get_extractor)]
StorageRepoDep = Annotated[DocumentStorageRepository, Depends(get_storage_repository)]
ChunkEnricherDep = Annotated[DocumentChunkEnricher, Depends(get_chunk_enricher)]


async def get_document_command_service(
    command_repo: DocumentCommandRepoDep,
    query_repo: DocumentQueryRepoDep,
    service_repo: ServiceRepoDep,
    vector_repo: VectorRepoDep,
    extractor: ExtractorDep,
    storage_repo: StorageRepoDep,
    chunk_enricher: ChunkEnricherDep,
) -> DocumentCommandService:
    """Construye el servicio de comandos para documentos."""
    return DocumentCommandService(
        command_repo=command_repo,
        query_repo=query_repo,
        service_repo=service_repo,
        vector_repo=vector_repo,
        extractor=extractor,
        storage_repo=storage_repo,
        chunk_enricher=chunk_enricher,
    )


async def get_document_query_service(sql_repo: DocumentQueryRepoDep) -> DocumentQueryService:
    """Construye un servicio de lectura para documentos."""
    return DocumentQueryService(sql_repo=sql_repo)
