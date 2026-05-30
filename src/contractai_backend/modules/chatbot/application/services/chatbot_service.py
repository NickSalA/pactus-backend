"""Service for handling chatbot logic."""

from typing import Any

from ....documents.domain.access_policy import get_readable_document_types
from ...application.dto import LLMResult
from ...application.repositories.base_llm import ILLMProvider
from ...domain.entities import ChatbotTokenUsage, ConversationTable, Message
from ...domain.exceptions import ConversationNotFoundError
from ...infrastructure.token_cost_calculator import TokenCostCalculator
from ...infrastructure.token_usage_repo import TokenUsageRepository
from .conversation_service import ConversationService

LIMIT_TITLE = 30


class ChatbotService:
    def __init__(
        self,
        llm_provider: ILLMProvider,
        conv_service: ConversationService,
        token_usage_repo: TokenUsageRepository | None = None,
    ):
        self.llm_provider: ILLMProvider = llm_provider
        self.conv_service: ConversationService = conv_service
        self.token_usage_repo: TokenUsageRepository | None = token_usage_repo
        self._cost_calculator = TokenCostCalculator()

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

    async def _create_conversation_with_initial_message(
        self,
        message: str,
        current_user,
        user_message: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        """Crea una nueva conversación y guarda el primer mensaje del usuario."""
        generated_title: str = f"{message[:LIMIT_TITLE]}..." if len(message) > LIMIT_TITLE else message
        saved_conv: ConversationTable = await self.conv_service.create_conversation(
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            title=generated_title,
            initial_messages=[user_message],
        )
        return saved_conv.id, user_message

    async def _append_user_message_to_conversation(
        self,
        thread_id: int,
        current_user,
        user_message: dict[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        """Añade un mensaje de usuario a una conversación existente."""
        updated_conversation: ConversationTable | None = await self.conv_service.append_messages(
            conversation_id=thread_id,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            new_messages=[user_message],
        )
        if not updated_conversation:
            raise ConversationNotFoundError(message=f"No se pudo sincronizar el historial. El thread_id {thread_id} no existe en la base de datos.")

        return thread_id, user_message

    async def _ensure_conversation_with_user_message(
        self,
        message: str,
        thread_id: int | None,
        current_user,
    ) -> tuple[int, dict[str, Any]]:
        """Garantiza que exista una conversación y añade el mensaje del usuario al historial.

        Si no existe una conversación, crea una nueva con un título generado a partir del mensaje.
        """
        user_message: dict[str, Any] = Message(role="user", content=message).as_record()

        if thread_id is None:
            return await self._create_conversation_with_initial_message(message=message, current_user=current_user, user_message=user_message)

        return await self._append_user_message_to_conversation(thread_id=thread_id, current_user=current_user, user_message=user_message)

    async def _append_bot_message(
        self,
        response_text: str,
        actual_thread_id: int,
        current_user,
    ) -> None:
        """Agrega el mensaje del bot al historial de la conversación.

        Lanza un error si la conversación objetivo no existe en la base de datos.
        """
        bot_message: dict[str, Any] = Message(role="bot", content=response_text).as_record()

        updated_conversation: ConversationTable | None = await self.conv_service.append_messages(
            conversation_id=actual_thread_id,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            new_messages=[bot_message],
        )

        if not updated_conversation:
            raise ConversationNotFoundError(
                message=f"No se pudo sincronizar el historial. El thread_id {actual_thread_id} no existe en la base de datos."
            )

    async def _persist_token_usage(
        self,
        conversation_id: int,
        llm_result: LLMResult,
        message_index: int,
    ) -> None:
        if self.token_usage_repo is None:
            return

        cost = self._cost_calculator.calculate(
            input_tokens=llm_result.input_tokens,
            output_tokens=llm_result.output_tokens,
        )

        token_usage = ChatbotTokenUsage(
            conversation_id=conversation_id,
            message_index=message_index,
            input_tokens=cost.input_tokens,
            output_tokens=cost.output_tokens,
            total_tokens=cost.total_tokens,
            input_cost_usd=cost.input_cost_usd,
            output_cost_usd=cost.output_cost_usd,
            total_cost_usd=cost.total_cost_usd,
            model_used=cost.model_used,
        )
        await self.token_usage_repo.save(token_usage)

    async def process_user_message(self, message: str, thread_id: int | None, current_user) -> tuple[str, int]:
        """Procesa un mensaje del usuario, obtiene la respuesta del LLM y actualiza la conversación en la base de datos."""
        thread_id, _ = await self._ensure_conversation_with_user_message(
            message=message,
            thread_id=thread_id,
            current_user=current_user,
        )

        llm_result = await self.llm_provider.invoke(
            message=message,
            thread_id=thread_id,
            user_context=self._build_user_context(current_user),
        )

        message_index = 1 if thread_id else 0
        await self._persist_token_usage(
            conversation_id=thread_id,
            llm_result=llm_result,
            message_index=message_index,
        )

        await self._append_bot_message(response_text=llm_result.response, actual_thread_id=llm_result.thread_id, current_user=current_user)

        return llm_result.response, llm_result.thread_id
