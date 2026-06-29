"""Repository port for contract activity audit records."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .....modules.audit.domain.entities import ContractActivityTable


class ContractActivityRepository(ABC):
    @abstractmethod
    async def record(self, activity: ContractActivityTable) -> ContractActivityTable:
        pass

    @abstractmethod
    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[ContractActivityTable]:
        pass
