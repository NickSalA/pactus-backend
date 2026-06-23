"""Application service for chatbot activity auditing."""

from collections.abc import Sequence

from contractai_backend.modules.audit.application.repositories import ChatbotActivityRepository
from contractai_backend.modules.audit.application.repositories.chatbot_activity_repo import ChatbotActivityWithConversationTitle
from contractai_backend.modules.audit.domain.entities import ChatbotActivityTable
from contractai_backend.modules.audit.domain.value_objs import AuditChatbotAction
from contractai_backend.modules.users.domain.entities import UserTable


class ChatbotActivityService:
    """Records and lists chatbot audit activity."""

    def __init__(self, repository: ChatbotActivityRepository) -> None:
        self.repository = repository

    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[ChatbotActivityWithConversationTitle]:
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
    ) -> ChatbotActivityTable:
        return await self._record(
            action=AuditChatbotAction.RESPONSE_GENERATED,
            actor=actor,
            conversation_id=conversation_id,
        )

    async def _record(
        self,
        *,
        action: AuditChatbotAction,
        actor: UserTable,
        conversation_id: int,
    ) -> ChatbotActivityTable:
        activity = ChatbotActivityTable(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            actor_name=actor.full_name or actor.email,
            actor_role=str(actor.role),
            action=action,
            conversation_id=conversation_id,
        )
        return await self.repository.record(activity)
