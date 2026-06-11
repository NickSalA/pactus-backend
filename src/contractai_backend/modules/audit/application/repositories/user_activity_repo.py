"""Repository port for user activity audit records."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from contractai_backend.modules.audit.domain.entities import UserActivityTable


class UserActivityRepository(ABC):
    @abstractmethod
    async def record(self, activity: UserActivityTable) -> UserActivityTable:
        """Persists a user activity audit record."""
        pass

    @abstractmethod
    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[UserActivityTable]:
        """Lists user activity for an organization ordered by newest first."""
        pass
