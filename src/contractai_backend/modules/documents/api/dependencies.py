"""Dependency Injection for the documents module."""

from typing import Annotated

import httpx
from fastapi import Depends
from qdrant_client import AsyncQdrantClient, QdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ....shared.infrastructure.database import get_aclient, get_client, get_session
from ....shared.infrastructure.http import get_http_client
from ...catalog.application.repositories import ServiceRepository
from ...catalog.application.services import ServiceCatalogService
from ...catalog.composition import build_service_catalog_service
from ...catalog.infrastructure.postgres_repo import SQLModelServiceRepository
from ...folders.application.repositories import FolderRepository
from ...folders.infrastructure.postgres_repo import SQLModelFolderRepository
from ..application.repositories import (
    DocumentChunkEnricher,
    DocumentCommandRepository,
    DocumentExtractor,
    DocumentQueryRepository,
    DocumentStorageRepository,
    DocumentStructuredExtractor,
    VectorRepository,
)
from ..application.services import DocumentCommandService, DocumentQueryService
from ..composition import build_document_command_service, build_document_query_service
from ..infrastructure import (
    GeminiDocumentStructuredExtractor,
    LlamaIndexQdrantRepository,
    LlamaParseExtractor,
    SQLModelDocumentCommandRepository,
    SQLModelDocumentQueryRepository,
    SupabaseStorageRepository,
    VectorChunkMetadataEnricher,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AsyncQdrantDep = Annotated[AsyncQdrantClient, Depends(get_aclient)]
SyncQdrantDep = Annotated[QdrantClient, Depends(get_client)]


async def get_document_query_repository(
    session: SessionDep,
) -> DocumentQueryRepository:
    """Construye el repositorio SQL de consultas para documentos."""
    return SQLModelDocumentQueryRepository(session=session)


async def get_document_command_repository(
    session: SessionDep,
) -> DocumentCommandRepository:
    """Construye el repositorio SQL de comandos para documentos."""
    return SQLModelDocumentCommandRepository(session=session)


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


async def get_structured_extractor() -> DocumentStructuredExtractor:
    """Construye el extractor estructurado para autofill best-effort."""
    return GeminiDocumentStructuredExtractor()


async def get_service_repository(session: SessionDep) -> ServiceRepository:
    """Builds the catalog repository used by document validation."""
    return SQLModelServiceRepository(session=session)


async def get_folder_repository(session: SessionDep) -> FolderRepository:
    """Builds the folder repository used by document validation."""
    return SQLModelFolderRepository(session=session)


async def get_service_catalog_service(repo: Annotated[ServiceRepository, Depends(get_service_repository)]) -> ServiceCatalogService:
    """Builds the catalog service used by compatibility document endpoints."""
    return build_service_catalog_service(repository=repo)


DocumentQueryRepoDep = Annotated[DocumentQueryRepository, Depends(get_document_query_repository)]
DocumentCommandRepoDep = Annotated[DocumentCommandRepository, Depends(get_document_command_repository)]
ServiceRepoDep = Annotated[ServiceRepository, Depends(get_service_repository)]
FolderRepoDep = Annotated[FolderRepository, Depends(get_folder_repository)]
VectorRepoDep = Annotated[VectorRepository, Depends(get_vector_repository)]
ExtractorDep = Annotated[DocumentExtractor, Depends(get_extractor)]
StorageRepoDep = Annotated[DocumentStorageRepository, Depends(get_storage_repository)]
ChunkEnricherDep = Annotated[DocumentChunkEnricher, Depends(get_chunk_enricher)]
StructuredExtractorDep = Annotated[DocumentStructuredExtractor, Depends(get_structured_extractor)]


async def get_document_command_service(
    command_repo: DocumentCommandRepoDep,
    query_repo: DocumentQueryRepoDep,
    service_repo: ServiceRepoDep,
    folder_repo: FolderRepoDep,
    vector_repo: VectorRepoDep,
    extractor: ExtractorDep,
    storage_repo: StorageRepoDep,
    chunk_enricher: ChunkEnricherDep,
    structured_extractor: StructuredExtractorDep,
) -> DocumentCommandService:
    """Construye el servicio de comandos para documentos."""
    return build_document_command_service(
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


async def get_document_query_service(sql_repo: DocumentQueryRepoDep) -> DocumentQueryService:
    """Construye un servicio de lectura para documentos."""
    return build_document_query_service(query_repo=sql_repo)
