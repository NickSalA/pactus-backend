"""Repository port for chatbot activity audit records."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from contractai_backend.modules.audit.domain.entities import ChatbotActivityTable


class ChatbotActivityRepository(ABC):
    @abstractmethod
    async def record(self, activity: ChatbotActivityTable) -> ChatbotActivityTable:
        """Persists a chatbot activity audit record."""
        pass

    @abstractmethod
    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[ChatbotActivityTable]:
        """Lists chatbot activity for an organization ordered by newest first."""
        pass
