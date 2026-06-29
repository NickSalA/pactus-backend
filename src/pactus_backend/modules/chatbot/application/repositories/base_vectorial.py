"""Repository interface for vector search in the institutional knowledge base."""

from abc import ABC, abstractmethod


class VectorRepository(ABC):
    @abstractmethod
    async def search_documents(self, query: str, limit: int = 5, document_ids: list[int] | None = None) -> str:
        """Search for relevant documents in the institutional knowledge base."""
        pass
