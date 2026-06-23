"""Repository port for AI token usage records."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from contractai_backend.modules.audit.domain.entities import AITokenUsageTable
from contractai_backend.modules.audit.domain.value_objs import AITokenSource


class AITokenUsageRepository(ABC):
    @abstractmethod
    async def record(self, usage: AITokenUsageTable) -> AITokenUsageTable:
        """Persists an AI token usage record."""
        pass

    @abstractmethod
    async def get_daily_token_usage_by_user(self, actor_user_id: int) -> int:
        """Calculates the sum of total_tokens used by the user today (UTC)."""
        pass

    @abstractmethod
    async def list_by_organization(
        self,
        organization_id: int,
        limit: int,
        offset: int,
        actor_user_id: int | None = None,
        source: AITokenSource | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Sequence[AITokenUsageTable]:
        """Lists AI token usage records for an organization with optional filters."""
        pass

    @abstractmethod
    async def get_summary_by_organization(
        self,
        organization_id: int,
        actor_user_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Gets aggregated token usage summary (total tokens, total cost) for an organization or user."""
        pass
