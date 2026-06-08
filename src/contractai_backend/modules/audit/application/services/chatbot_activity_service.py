"""Application service for chatbot activity auditing."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol

from contractai_backend.modules.audit.application.repositories import ChatbotActivityRepository
from contractai_backend.modules.audit.domain.entities import ChatbotActivityTable
from contractai_backend.modules.audit.domain.value_objs import AuditChatbotAction
from contractai_backend.modules.users.domain.entities import UserTable


class ChatbotTokenCost(Protocol):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    model_used: str


class ChatbotActivityService:
    """Records and lists chatbot audit activity."""

    def __init__(self, repository: ChatbotActivityRepository) -> None:
        self.repository = repository

    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[ChatbotActivityTable]:
        return await self.repository.list_by_organization(organization_id=organization_id, limit=limit, offset=offset)

    async def record_conversation_started(self, *, actor: UserTable, conversation_id: int) -> ChatbotActivityTable:
        return await self._record(action=AuditChatbotAction.CONVERSATION_STARTED, actor=actor, conversation_id=conversation_id)

    async def record_message_sent(self, *, actor: UserTable, conversation_id: int) -> ChatbotActivityTable:
        return await self._record(action=AuditChatbotAction.MESSAGE_SENT, actor=actor, conversation_id=conversation_id)

    async def record_response_generated(
        self,
        *,
        actor: UserTable,
        conversation_id: int,
        cost: ChatbotTokenCost,
    ) -> ChatbotActivityTable:
        return await self._record(
            action=AuditChatbotAction.RESPONSE_GENERATED,
            actor=actor,
            conversation_id=conversation_id,
            input_tokens=cost.input_tokens,
            output_tokens=cost.output_tokens,
            total_tokens=cost.total_tokens,
            input_cost_usd=Decimal(str(cost.input_cost_usd)),
            output_cost_usd=Decimal(str(cost.output_cost_usd)),
            total_cost_usd=Decimal(str(cost.total_cost_usd)),
            model_used=cost.model_used,
        )

    async def _record(
        self,
        *,
        action: AuditChatbotAction,
        actor: UserTable,
        conversation_id: int,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        input_cost_usd: Decimal | None = None,
        output_cost_usd: Decimal | None = None,
        total_cost_usd: Decimal | None = None,
        model_used: str | None = None,
    ) -> ChatbotActivityTable:
        activity = ChatbotActivityTable(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            actor_name=actor.full_name or actor.email,
            actor_role=str(actor.role),
            action=action,
            conversation_id=conversation_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            input_cost_usd=input_cost_usd,
            output_cost_usd=output_cost_usd,
            total_cost_usd=total_cost_usd,
            model_used=model_used,
        )
        return await self.repository.record(activity)
