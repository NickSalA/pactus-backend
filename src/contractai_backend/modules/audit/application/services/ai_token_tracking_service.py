"""Application service for tracking AI token usage globally."""

from decimal import Decimal
from typing import Protocol

from contractai_backend.modules.audit.application.repositories import AITokenUsageRepository
from contractai_backend.modules.audit.domain.entities import AITokenUsageTable
from contractai_backend.modules.audit.domain.exceptions import LLMQuotaExceededError
from contractai_backend.modules.audit.domain.value_objs import AITokenSource
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.shared.config import settings


class ChatbotTokenCost(Protocol):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    model_used: str


class AITokenTrackingService:
    """Records global AI token usage and validates rate limits."""

    def __init__(self, repository: AITokenUsageRepository) -> None:
        self.repository = repository

    async def check_rate_limit(self, actor: UserTable) -> None:
        """Validates if the user has exceeded their daily token limit."""
        if actor.id is None:
            return

        daily_tokens = await self.repository.get_daily_token_usage_by_user(actor_user_id=actor.id)
        if daily_tokens >= settings.MAX_DAILY_TOKENS_PER_USER:
            raise LLMQuotaExceededError()

    async def record_usage(
        self,
        *,
        source: AITokenSource,
        actor: UserTable,
        cost: ChatbotTokenCost,
    ) -> AITokenUsageTable:
        """Records token consumption for an AI invocation."""
        usage = AITokenUsageTable(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            source=source,
            input_tokens=cost.input_tokens,
            output_tokens=cost.output_tokens,
            total_tokens=cost.total_tokens,
            input_cost_usd=Decimal(str(cost.input_cost_usd)),
            output_cost_usd=Decimal(str(cost.output_cost_usd)),
            total_cost_usd=Decimal(str(cost.total_cost_usd)),
            model_used=cost.model_used,
        )
        return await self.repository.record(usage)
