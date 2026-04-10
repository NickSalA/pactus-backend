"""Repository for managing conversations in the database."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.core.infrastructure.base import PostgresBaseRepository
from contractai_backend.modules.chatbot.application.repositories import IConversationRepository
from contractai_backend.modules.chatbot.domain import ConversationTable


class ConversationRepository(PostgresBaseRepository[ConversationTable], IConversationRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(model=ConversationTable, session=session)

    async def get_visible_by_id(self, conversation_id: int, user_id: int, organization_id: int) -> ConversationTable | None:
        """Loads a conversation only if it belongs to the requested user within the org."""
        query = (
            select(self.model)
            .where(self.model.id == conversation_id)
            .where(self.model.user_id == user_id)
            .where(self.model.organization_id == organization_id)
        )
        result = await self.session.exec(statement=query)
        return result.first()

    async def update_messages(
        self,
        conversation_id: int,
        organization_id: int,
        user_id: int,
        new_messages: list[dict[str, Any]],
    ) -> ConversationTable | None:
        """Actualiza el contenido de una conversación existente agregando nuevos mensajes."""
        db_obj = await self.get_visible_by_id(
            conversation_id=conversation_id,
            user_id=user_id,
            organization_id=organization_id,
        )
        if not db_obj:
            return None

        current_content: list[dict[str, Any]] = list(db_obj.content)
        current_content.extend(new_messages)

        db_obj.content = current_content
        db_obj.updated_at: datetime = datetime.now(tz=UTC)

        self.session.add(instance=db_obj)
        await self.session.commit()
        await self.session.refresh(instance=db_obj)

        return db_obj

    async def get_by_user(self, user_id: int, organization_id: int) -> Sequence[ConversationTable]:
        """Obtiene una lista de conversaciones asociadas a un usuario específico, ordenadas por fecha de creación descendente."""
        query = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .where(self.model.organization_id == organization_id)
            .order_by(desc(column=self.model.created_at))
        )
        result = await self.session.exec(statement=query)
        return result.all()
