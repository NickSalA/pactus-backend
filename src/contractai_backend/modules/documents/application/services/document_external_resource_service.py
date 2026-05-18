"""Coordinates external document resources such as files and vectors."""

from typing import Any

from loguru import logger

from ...domain.value_objs import DocumentType
from ..repositories import DocumentStorageRepository, VectorRepository


class DocumentExternalResourceService:
    """Wraps storage and vector operations used by document commands."""

    def __init__(self, storage_repo: DocumentStorageRepository, vector_repo: VectorRepository):
        """Stores external resource adapters."""
        self.storage_repo = storage_repo
        self.vector_repo = vector_repo

    async def upload_file(
        self,
        *,
        document_id: int,
        organization_id: int,
        document_type: DocumentType | None,
        file: bytes,
        filename: str,
        content_type: str,
    ) -> str:
        """Uploads a document file and returns its storage path."""
        return await self.storage_repo.upload_file(
            document_id=document_id,
            organization_id=organization_id,
            document_type=document_type,
            file=file,
            filename=filename,
            content_type=content_type,
        )

    async def add_vectors(self, *, index_name: str, document_id: int, chunks: list[Any]) -> None:
        """Indexes parsed document chunks in the vector store."""
        await self.vector_repo.add_vectors(index_name=index_name, document_id=document_id, chunks=chunks)

    async def delete_vectors(self, *, index_name: str, document_id: int) -> None:
        """Deletes document vectors from one vector index."""
        await self.vector_repo.delete_vectors(index_name=index_name, document_id=document_id)

    async def delete_vectors_from_indexes(self, *, index_names: tuple[str, ...], document_id: int) -> None:
        """Deletes document vectors from all requested indexes."""
        for index_name in index_names:
            await self.delete_vectors(index_name=index_name, document_id=document_id)

    async def delete_file_safely(self, path: str | None) -> None:
        """Best-effort file cleanup used by compensation flows."""
        if path is None:
            return
        try:
            await self.storage_repo.delete_file(path=path)
        except Exception as exc:
            logger.exception(f"Failed to delete document file from storage: {exc!s}")

    async def create_signed_url(self, *, path: str, expires_in: int) -> str:
        """Creates a temporary signed URL for a stored document file."""
        return await self.storage_repo.create_signed_url(path=path, expires_in=expires_in)


class DocumentCreationCompensationService:
    """Runs best-effort cleanup when document creation fails after SQL persistence."""

    def __init__(self, external_resources: DocumentExternalResourceService):
        """Stores external resource cleanup dependencies."""
        self.external_resources = external_resources

    async def compensate(
        self,
        *,
        document_id: int,
        index_name: str,
        storage_path: str | None,
        vectors_added: bool,
        delete_document,
    ) -> None:
        """Deletes partially created vectors, files and SQL rows without masking the original error."""
        if vectors_added:
            try:
                await self.external_resources.delete_vectors(index_name=index_name, document_id=document_id)
            except Exception as exc:
                logger.exception(f"Failed to delete document vectors during compensation: {exc!s}")

        if storage_path:
            await self.external_resources.delete_file_safely(storage_path)

        try:
            await delete_document(id=document_id)
        except Exception as exc:
            logger.exception(f"Failed to delete document row during compensation: {exc!s}")
