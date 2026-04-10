"""Service for handling conversation logic."""

from typing import Any

from ...domain.entities import ConversationTable
from ..repositories.base_conversation import IConversationRepository


class ConversationService:
    def __init__(self, repository: IConversationRepository):
        self.repository: IConversationRepository = repository

    async def create_conversation(
        self,
        *,
        organization_id: int,
        user_id: int,
        title: str,
        initial_messages: list[dict[str, Any]] | None = None,
    ) -> ConversationTable:
        """Crea una nueva conversación en la base de datos a partir de los datos proporcionados."""
        new_conv = ConversationTable(
            organization_id=organization_id,
            user_id=user_id,
            title=title,
            content=list(initial_messages or []),
        )
        saved_conv = await self.repository.save(new_conv)
        return ConversationTable.model_validate(obj=saved_conv)

    async def get_conversation(self, conversation_id: int, organization_id: int, user_id: int) -> ConversationTable | None:
        """Obtiene una conversación por su ID. Devuelve None si no existe."""
        conversation = await self.repository.get_visible_by_id(
            conversation_id=conversation_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if not conversation:
            return None
        return ConversationTable.model_validate(conversation)

    async def list_user_conversations(self, organization_id: int, user_id: int) -> list[ConversationTable]:
        """Obtiene una lista de conversaciones asociadas a un usuario específico."""
        conversations = await self.repository.get_by_user(user_id=user_id, organization_id=organization_id)
        return [ConversationTable.model_validate(conv) for conv in conversations]

    async def append_messages(
        self,
        *,
        conversation_id: int,
        organization_id: int,
        user_id: int,
        new_messages: list[dict[str, Any]],
    ) -> ConversationTable | None:
        """Agrega nuevos mensajes al contenido de una conversación existente. Devuelve la conversación actualizada o None si no se encuentra."""
        updated_conv = await self.repository.update_messages(
            conversation_id=conversation_id,
            organization_id=organization_id,
            user_id=user_id,
            new_messages=new_messages,
        )
        if not updated_conv:
            return None
        return ConversationTable.model_validate(obj=updated_conv)
