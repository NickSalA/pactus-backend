"""Relational repository contracts for the documents module."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from ..dto import ContractQueryDTO
from ...domain import DocumentServiceTable, DocumentTable


class DocumentQueryRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: int) -> DocumentTable | None:
        """Returns one document by id."""
        pass

    @abstractmethod
    async def get_all(self, filters: dict[str, Any] | None = None, limit: int | None = None, offset: int | None = None) -> Sequence[DocumentTable]:
        """Lists documents matching optional filters with optional pagination."""
        pass

    @abstractmethod
    async def get_document_services(self, doc_id: int) -> Sequence[DocumentServiceTable]:
        """Lists service items for one document."""
        pass

    @abstractmethod
    async def get_document_services_by_document_ids(self, document_ids: Sequence[int]) -> dict[int, Sequence[DocumentServiceTable]]:
        """Lists service items grouped by document id."""
        pass

    @abstractmethod
    async def search_contract_access_candidates(
        self,
        organization_id: int,
        query: str,
        limit: int = 10,
        chatbot_ready_only: bool = False,
        state: str | None = None,
    ) -> Sequence[dict[str, Any]]:
        """Lists contracts whose counterparty may match a user-provided name for access decisions."""
        pass

    @abstractmethod
    async def search_contracts(
        self,
        organization_id: int,
        query: ContractQueryDTO,
        limit: int | None = None,
        chatbot_ready_only: bool = False,
    ) -> Sequence[DocumentTable]:
        """Lists contracts matching structured filters."""
        pass

    @abstractmethod
    async def count_contracts(
        self,
        organization_id: int,
        query: ContractQueryDTO,
        chatbot_ready_only: bool = False,
    ) -> int:
        """Counts contracts matching structured filters."""
        pass

    @abstractmethod
    async def rank_contracts_by_client(
        self,
        organization_id: int,
        query: ContractQueryDTO,
        limit: int | None = None,
        chatbot_ready_only: bool = False,
    ) -> Sequence[dict[str, Any]]:
        """Returns a client ranking based on filtered contracts."""
        pass

    @abstractmethod
    async def sync_contract_states(self, organization_id: int) -> int:
        """Synchronizes persisted document states for one organization."""
        pass


class DocumentCommandRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: int) -> DocumentTable | None:
        """Returns one document by id."""
        pass

    @abstractmethod
    async def save(self, entity: DocumentTable) -> DocumentTable:
        """Persists a new document."""
        pass

    @abstractmethod
    async def update(self, entity: DocumentTable) -> DocumentTable:
        """Persists changes to a document."""
        pass

    @abstractmethod
    async def delete(self, id: int) -> bool:
        """Deletes a document by id."""
        pass

    @abstractmethod
    async def replace_document_services(self, doc_id: int, service_items: Sequence[DocumentServiceTable]) -> Sequence[DocumentServiceTable]:
        """Replaces all service items for a document."""
        pass
