"""Repository port for AI token usage records."""

from abc import ABC, abstractmethod

from contractai_backend.modules.audit.domain.entities import AITokenUsageTable


class AITokenUsageRepository(ABC):
    @abstractmethod
    async def record(self, usage: AITokenUsageTable) -> AITokenUsageTable:
        """Persists an AI token usage record."""
        pass

    @abstractmethod
    async def get_daily_token_usage_by_user(self, actor_user_id: int) -> int:
        """Calculates the sum of total_tokens used by the user today (UTC)."""
        pass
