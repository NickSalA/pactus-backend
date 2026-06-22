"""Service for handling chatbot logic."""

from typing import Any

from loguru import logger

from ....audit.application.services import AITokenTrackingService, ChatbotActivityService
from ....audit.domain.value_objs import AITokenSource
from ....documents.domain.access_policy import get_readable_document_types
from ...application.dto import ChartData, LLMResult, TokenCostResult
from ...application.repositories.base_llm import ILLMProvider
from ...domain.entities import ConversationTable, Message
from ...domain.exceptions import ConversationNotFoundError
from ...infrastructure.token_cost_calculator import TokenCostCalculator
from .conversation_service import ConversationService

LIMIT_TITLE = 30


class ChatbotService:
    def __init__(
        self,
        llm_provider: ILLMProvider,
        conv_service: ConversationService,
        chatbot_activity_service: ChatbotActivityService | None = None,
        ai_token_tracking_service: AITokenTrackingService | None = None,
    ):
        self.llm_provider: ILLMProvider = llm_provider
        self.conv_service: ConversationService = conv_service
        self.chatbot_activity_service = chatbot_activity_service
        self.ai_token_tracking_service = ai_token_tracking_service
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
        if self.chatbot_activity_service:
            await self.chatbot_activity_service.record_conversation_started(actor=current_user, conversation_id=saved_conv.id)
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
            conversation_id, stored_message = await self._create_conversation_with_initial_message(
                message=message,
                current_user=current_user,
                user_message=user_message,
            )
        else:
            conversation_id, stored_message = await self._append_user_message_to_conversation(
                thread_id=thread_id,
                current_user=current_user,
                user_message=user_message,
            )

        if self.chatbot_activity_service:
            await self.chatbot_activity_service.record_message_sent(actor=current_user, conversation_id=conversation_id)
        return conversation_id, stored_message

    async def _append_bot_message(
        self,
        response_text: str,
        actual_thread_id: int,
        current_user,
        chart: ChartData | None = None,
    ) -> None:
        """Agrega el mensaje del bot al historial de la conversación.

        Lanza un error si la conversación objetivo no existe en la base de datos.
        """
        chart_dict = chart.model_dump(mode="json") if chart else None
        bot_message: dict[str, Any] = Message(role="bot", content=response_text, chart=chart_dict).as_record()

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

    def _calculate_token_usage(
        self,
        conversation_id: int,
        llm_result: LLMResult,
    ) -> TokenCostResult:
        cost = self._cost_calculator.calculate(
            input_tokens=llm_result.input_tokens,
            output_tokens=llm_result.output_tokens,
        )

        logger.info(
            "Calculated token usage for conversation_id %s: Input: %s, Output: %s, Total: %s, Cost: $%s USD using model %s",
            conversation_id,
            cost.input_tokens,
            cost.output_tokens,
            cost.total_tokens,
            cost.total_cost_usd,
            cost.model_used,
        )
        return cost

    async def process_user_message(self, message: str, thread_id: int | None, current_user) -> tuple[str, int, ChartData | None]:
        """Procesa un mensaje del usuario, obtiene la respuesta del LLM y actualiza la conversación en la base de datos."""
        thread_id, _ = await self._ensure_conversation_with_user_message(
            message=message,
            thread_id=thread_id,
            current_user=current_user,
        )

        if self.ai_token_tracking_service:
            await self.ai_token_tracking_service.check_rate_limit(actor=current_user)

        llm_result = await self.llm_provider.invoke(
            message=message,
            thread_id=thread_id,
            user_context=self._build_user_context(current_user),
        )

        cost = self._calculate_token_usage(
            conversation_id=thread_id,
            llm_result=llm_result,
        )
        if self.chatbot_activity_service:
            await self.chatbot_activity_service.record_response_generated(actor=current_user, conversation_id=thread_id)
        if self.ai_token_tracking_service:
            await self.ai_token_tracking_service.record_usage(source=AITokenSource.CHATBOT, actor=current_user, cost=cost)

        await self._append_bot_message(
            response_text=llm_result.response,
            actual_thread_id=llm_result.thread_id,
            current_user=current_user,
            chart=llm_result.chart,
        )

        return llm_result.response, llm_result.thread_id, llm_result.chart
