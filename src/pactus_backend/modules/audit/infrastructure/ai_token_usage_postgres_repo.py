"""SQLModel implementation of AITokenUsageRepository."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlmodel import desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....modules.audit.application.repositories import AITokenUsageRepository
from ....modules.audit.domain.entities import AITokenUsageTable
from ....modules.audit.domain.value_objs import AITokenSource


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
        statement = (
            select(AITokenUsageTable)
            .where(AITokenUsageTable.organization_id == organization_id)
            .order_by(desc(AITokenUsageTable.created_at))
            .offset(offset)
            .limit(limit)
        )
        if actor_user_id is not None:
            statement = statement.where(AITokenUsageTable.actor_user_id == actor_user_id)
        if source is not None:
            statement = statement.where(AITokenUsageTable.source == source)
        if start_date is not None:
            statement = statement.where(AITokenUsageTable.created_at >= start_date)
        if end_date is not None:
            statement = statement.where(AITokenUsageTable.created_at <= end_date)

        result = await self.session.exec(statement)
        return result.all()

    async def get_summary_by_organization(
        self,
        organization_id: int,
        actor_user_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Gets aggregated token usage summary (total tokens, total cost) for an organization or user."""
        statement = select(
            func.sum(AITokenUsageTable.total_tokens).label("total_tokens"),
            func.sum(AITokenUsageTable.total_cost_usd).label("total_cost_usd"),
            func.sum(AITokenUsageTable.input_tokens).label("input_tokens"),
            func.sum(AITokenUsageTable.output_tokens).label("output_tokens"),
        ).where(AITokenUsageTable.organization_id == organization_id)

        if actor_user_id is not None:
            statement = statement.where(AITokenUsageTable.actor_user_id == actor_user_id)
        if start_date is not None:
            statement = statement.where(AITokenUsageTable.created_at >= start_date)
        if end_date is not None:
            statement = statement.where(AITokenUsageTable.created_at <= end_date)

        result = await self.session.exec(statement)
        row = result.first()
        if not row or row[0] is None:
            return {
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
            }

        return {
            "total_tokens": row[0],
            "total_cost_usd": float(row[1] or 0),
            "input_tokens": row[2] or 0,
            "output_tokens": row[3] or 0,
        }
