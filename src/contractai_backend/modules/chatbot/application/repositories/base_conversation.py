"""Repository for managing conversations in the database."""

from abc import abstractmethod
from collections.abc import Sequence
from typing import Any

from .....core.application.base import BaseRepository
from ...domain.entities import ConversationTable


class IConversationRepository(BaseRepository[ConversationTable]):
    @abstractmethod
    async def update_messages(
        self,
        conversation_id: int,
        organization_id: int,
        user_id: int,
        new_messages: list[dict[str, Any]],
    ) -> ConversationTable | None:
        """Actualiza el contenido de una conversación existente agregando nuevos mensajes."""
        pass

    @abstractmethod
    async def get_by_user(self, user_id: int, organization_id: int) -> Sequence[ConversationTable]:
        """Obtiene una lista de conversaciones asociadas a un usuario específico."""
        pass

    @abstractmethod
    async def get_visible_by_id(self, conversation_id: int, user_id: int, organization_id: int) -> ConversationTable | None:
        """Returns a conversation only when it belongs to the given user and organization."""
        pass
