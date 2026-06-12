"""Repository port for contract activity audit records."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from contractai_backend.modules.audit.domain.entities import ContractActivityTable


class ContractActivityRepository(ABC):
    @abstractmethod
    async def record(self, activity: ContractActivityTable) -> ContractActivityTable:
        """Persists a contract activity audit record."""
        pass

    @abstractmethod
    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[ContractActivityTable]:
        """Lists contract activity for an organization ordered by newest first."""
        pass
