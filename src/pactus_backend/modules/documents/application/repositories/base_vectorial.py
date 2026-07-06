"""Contracts for vector indexing and retrieval."""
from abc import ABC, abstractmethod
from typing import Any


class VectorRepository(ABC):
    """Stores vectorized document chunks and retrieves similar content."""

    @abstractmethod
    async def add_vectors(self, index_name: str, document_id: int, chunks: list[Any]) -> None:
        """Adds vectorized chunks for a document."""
        pass

    @abstractmethod
    async def delete_vectors(self, index_name: str, document_id: int) -> None:
        """Deletes all vectors associated with a document."""
        pass
