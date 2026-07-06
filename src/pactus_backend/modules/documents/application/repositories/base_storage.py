"""Interface for document binary storage providers."""

from abc import ABC, abstractmethod

from ...domain.value_objs import DocumentType


class DocumentStorageRepository(ABC):
    """Defines operations to store, remove and share document files."""

    @abstractmethod
    async def upload_file(
        self,
        document_id: int,
        organization_id: int,
        document_type: DocumentType | None,
        file: bytes,
        filename: str,
        content_type: str,
    ) -> str:
        """Uploads a document file to storage."""

    @abstractmethod
    async def delete_file(self, path: str) -> None:
        """Deletes a document file from storage if it exists."""

    @abstractmethod
    async def create_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """Creates a signed URL for temporary file access."""
