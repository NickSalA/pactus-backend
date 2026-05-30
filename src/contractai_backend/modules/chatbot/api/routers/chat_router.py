"""Define el router para las operaciones relacionadas con el chatbot, incluyendo el envío de mensajes y la gestión de conversaciones."""

from typing import Annotated

from fastapi import APIRouter, Depends

from .....modules.users.domain.entities import UserTable
from .....shared.api.dependencies.security import get_current_user
from ...api.dependencies import get_chatbot_service
from ...api.schemas import ChatRequest, ChatResponse
from ...application.services import ChatbotService

router = APIRouter()

ChatbotServiceDep = Annotated[ChatbotService, Depends(get_chatbot_service)]
CurrentUserDep = Annotated[UserTable, Depends(get_current_user)]


@router.post("/", response_model=ChatResponse)
async def send_chat_message(request: ChatRequest, service: ChatbotServiceDep, current_user: CurrentUserDep) -> ChatResponse:
    """Endpoint para enviar un mensaje al chatbot. Procesa el mensaje, obtiene la respuesta y actualiza la conversación."""
    respuesta, thread_id, chart = await service.process_user_message(message=request.message, thread_id=request.thread_id, current_user=current_user)

    return ChatResponse(response=respuesta, thread_id=thread_id, chart=chart)
