"""Service for managing token usage analytics."""

from collections.abc import Sequence
from decimal import Decimal

from ...domain.entities import ChatbotTokenUsage
from ...infrastructure.token_usage_repo import TokenUsageRepository
from ..dto import TokenUsageSummaryDTO
from ..repositories import IConversationRepository


class TokenUsageService:
    def __init__(self, usage_repo: TokenUsageRepository, conv_repo: IConversationRepository):
        self.usage_repo = usage_repo
        self.conv_repo = conv_repo

    async def get_conversation_usage(self, conversation_id: int) -> Sequence[ChatbotTokenUsage]:
        """Obtiene el historial de uso de tokens de una conversación específica."""
        return await self.usage_repo.get_by_conversation_id(conversation_id)

    async def get_summary(self, user_id: int, organization_id: int, conversation_id: int | None = None) -> TokenUsageSummaryDTO:
        """Calcula el resumen de uso de tokens del usuario o de una conversación."""
        usage_records: list[ChatbotTokenUsage] = []

        async with self.usage_repo.session:
            if conversation_id is not None:
                usage = await self.usage_repo.get_by_conversation_id(conversation_id)
                usage_records.extend(usage)
            else:
                conversations = await self.conv_repo.get_by_user(user_id=user_id, organization_id=organization_id)

                # Fetch usage for each conversation
                for conv in conversations:
                    if conv.id is not None:
                        usage = await self.usage_repo.get_by_conversation_id(conv.id)
                        usage_records.extend(usage)

        if not usage_records:
            return TokenUsageSummaryDTO(
                total_input_tokens=0,
                total_output_tokens=0,
                total_tokens=0,
                total_input_cost_usd=Decimal("0"),
                total_output_cost_usd=Decimal("0"),
                total_cost_usd=Decimal("0"),
                usage_count=0,
            )

        return TokenUsageSummaryDTO(
            total_input_tokens=sum(r.input_tokens for r in usage_records),
            total_output_tokens=sum(r.output_tokens for r in usage_records),
            total_tokens=sum(r.total_tokens for r in usage_records),
            total_input_cost_usd=Decimal(str(sum(r.input_cost_usd for r in usage_records))),
            total_output_cost_usd=Decimal(str(sum(r.output_cost_usd for r in usage_records))),
            total_cost_usd=Decimal(str(sum(r.total_cost_usd for r in usage_records))),
            usage_count=len(usage_records),
        )
