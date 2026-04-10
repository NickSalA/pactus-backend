"""Service for handling chatbot logic."""

from typing import Any

from ....documents.domain.access_policy import get_readable_document_types
from ...application.repositories.base_llm import ILLMProvider
from ...domain.entities import ConversationTable, Message
from ...domain.exceptions import ConversationNotFoundError
from .conversation_service import ConversationService

LIMIT_TITLE = 30


class ChatbotService:
    def __init__(self, llm_provider: ILLMProvider, conv_service: ConversationService):
        self.llm_provider: ILLMProvider = llm_provider
        self.conv_service: ConversationService = conv_service

    @staticmethod
    def _build_user_context(current_user: Any) -> dict[str, Any]:
        """Build the trusted backend context passed into the chatbot graph."""
        role = getattr(current_user, "role", None)
        resolved_role = getattr(role, "value", role)
        readable_document_types = get_readable_document_types(role)
        return {
            "user_id": getattr(current_user, "id", None),
            "organization_id": getattr(current_user, "organization_id", None),
            "role": str(resolved_role) if resolved_role is not None else "",
            "full_name": getattr(current_user, "full_name", None),
            "allowed_document_types": None
            if readable_document_types is None
            else [document_type.value for document_type in sorted(readable_document_types, key=lambda value: value.value)],
        }

    async def process_user_message(self, message: str, thread_id: int | None, current_user) -> tuple[str, int]:
        """Procesa un mensaje del usuario, obtiene la respuesta del LLM y actualiza la conversación en la base de datos."""
        user_message = Message(role="user", content=message).as_record()

        if thread_id is None:
            generated_title: str = message[:LIMIT_TITLE] + "..." if len(message) > LIMIT_TITLE else message
            saved_conv = await self.conv_service.create_conversation(
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                title=generated_title,
                initial_messages=[user_message],
            )
            thread_id: int = saved_conv.id
        else:
            updated_conversation = await self.conv_service.append_messages(
                conversation_id=thread_id,
                organization_id=current_user.organization_id,
                user_id=current_user.id,
                new_messages=[user_message],
            )
            if not updated_conversation:
                raise ConversationNotFoundError(
                    message=f"No se pudo sincronizar el historial. El thread_id {thread_id} no existe en la base de datos."
                )

        response_text, actual_thread_id = await self.llm_provider.invoke(
            message=message,
            thread_id=thread_id,
            user_context=self._build_user_context(current_user),
        )

        bot_message = Message(role="bot", content=response_text).as_record()

        updated_conversation = await self.conv_service.append_messages(
            conversation_id=actual_thread_id,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            new_messages=[bot_message],
        )

        if not updated_conversation:
            raise ConversationNotFoundError(
                message=f"No se pudo sincronizar el historial. El thread_id {actual_thread_id} no existe en la base de datos."
            )

        return response_text, actual_thread_id
