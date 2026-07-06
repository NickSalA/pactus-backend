"""Routes related to conversations."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from .....core.exceptions.base import ForbiddenError
from .....shared.api.dependencies.security import CurrentUserDep
from ...api.dependencies import get_conversation_service
from ...api.schemas import ConversationList, ConversationRead, ConversationUpdate
from ...application import ConversationService
from ...domain import ConversationNotFoundError

router = APIRouter()
ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]


@router.get(path="/user/{user_id}", response_model=list[ConversationList])
async def list_my_conversations(user_id: int, service: ConversationServiceDep, current_user: CurrentUserDep):
    """Endpoint para listar las conversaciones de un usuario específico."""
    if user_id != current_user.id:
        raise ForbiddenError("No tiene permisos para acceder a las conversaciones de otro usuario")

    conversations = await service.list_user_conversations(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )
    return [ConversationList.model_validate(conversation) for conversation in conversations]


@router.get(path="/{conversation_id}", response_model=ConversationRead)
async def get_single_conversation(conversation_id: int, service: ConversationServiceDep, current_user: CurrentUserDep):
    """Endpoint para obtener una conversación específica."""
    conversation = await service.get_conversation(
        conversation_id=conversation_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )
    if not conversation:
        raise ConversationNotFoundError()
    return ConversationRead.model_validate(conversation)


@router.patch(path="/{conversation_id}", response_model=ConversationRead)
async def update_conversation_title(
    conversation_id: int,
    payload: ConversationUpdate,
    service: ConversationServiceDep,
    current_user: CurrentUserDep,
):
    """Endpoint para actualizar el título de una conversación."""
    conversation = await service.update_conversation_title(
        conversation_id=conversation_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        title=payload.title,
    )
    if not conversation:
        raise ConversationNotFoundError()
    return ConversationRead.model_validate(conversation)


@router.delete(path="/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_conversation(conversation_id: int, service: ConversationServiceDep, current_user: CurrentUserDep) -> None:
    """Endpoint para eliminar una conversación del usuario autenticado."""
    deleted = await service.delete_conversation(
        conversation_id=conversation_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise ConversationNotFoundError()
