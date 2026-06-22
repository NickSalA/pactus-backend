"""SQLModel implementation of AITokenUsageRepository."""

from datetime import UTC, datetime

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.audit.application.repositories import AITokenUsageRepository
from contractai_backend.modules.audit.domain.entities import AITokenUsageTable


class SQLModelAITokenUsageRepository(AITokenUsageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, usage: AITokenUsageTable) -> AITokenUsageTable:
        """Persists an AI token usage record."""
        self.session.add(usage)
        await self.session.commit()
        await self.session.refresh(usage)
        return usage

    async def get_daily_token_usage_by_user(self, actor_user_id: int) -> int:
        """Calculates the sum of total_tokens used by the user today (UTC)."""
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        statement = (
            select(func.sum(AITokenUsageTable.total_tokens))
            .where(AITokenUsageTable.actor_user_id == actor_user_id)
            .where(AITokenUsageTable.created_at >= today_start)
        )

        result = await self.session.exec(statement)
        total = result.one_or_none()
        return total or 0
