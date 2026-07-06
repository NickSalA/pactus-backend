"""Repository port for template activity audit records."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .....modules.audit.domain.entities import TemplateActivityTable


class TemplateActivityRepository(ABC):
    @abstractmethod
    async def record(self, activity: TemplateActivityTable) -> TemplateActivityTable:
        """Persists a template activity audit record."""
        pass

    @abstractmethod
    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[TemplateActivityTable]:
        """Lists template activity for an organization ordered by newest first."""
        pass
