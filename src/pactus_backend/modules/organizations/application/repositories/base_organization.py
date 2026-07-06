"""Organization repository contracts."""

from abc import abstractmethod

from .....core.application.base import BaseRepository
from .....modules.organizations.domain.entities import OrganizationTable


class OrganizationRepository(BaseRepository[OrganizationTable]):
    """Base repository for organization persistence."""

    @abstractmethod
    async def get_by_name(self, name: str) -> OrganizationTable | None:
        """Retrieve an organization by its name."""
        pass

    @abstractmethod
    async def get_by_ruc(self, ruc: str) -> OrganizationTable | None:
        """Retrieve an organization by its RUC."""
        pass
