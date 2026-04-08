"""Repository contracts for the service catalog module."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from ..domain.entities import ServiceTable


class ServiceRepository(ABC):
    @abstractmethod
    async def get_services_by_ids(self, organization_id: int, service_ids: Sequence[int]) -> Sequence[ServiceTable]:
        """Returns catalog services for the given ids."""
        pass

    @abstractmethod
    async def get_services(self, organization_id: int, *, include_inactive: bool = False) -> Sequence[ServiceTable]:
        """Lists the catalog for one organization."""
        pass

    @abstractmethod
    async def get_service_by_id(self, organization_id: int, service_id: int) -> ServiceTable | None:
        """Returns one service by id within an organization."""
        pass

    @abstractmethod
    async def get_service_by_name(self, organization_id: int, name: str) -> ServiceTable | None:
        """Returns one service by normalized name within an organization."""
        pass

    @abstractmethod
    async def save_service(self, entity: ServiceTable) -> ServiceTable:
        """Creates a new catalog service."""
        pass

    @abstractmethod
    async def update_service(self, entity: ServiceTable) -> ServiceTable:
        """Persists changes to a catalog service."""
        pass

    @abstractmethod
    async def delete_service(self, service_id: int) -> bool:
        """Deletes a catalog service by id."""
        pass

    @abstractmethod
    async def count_documents_by_service_ids(self, organization_id: int, service_ids: Sequence[int]) -> dict[int, int]:
        """Counts contracts linked to each service id."""
        pass
