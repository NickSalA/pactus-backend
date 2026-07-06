"""Router for chatbot activity audit queries."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from .....core.exceptions.base import ForbiddenError
from .....shared.api.dependencies.security import CurrentUserDep
from ....users.domain.value_objs import UserRole
from ...application.services import ChatbotActivityService
from ..dependencies import get_chatbot_activity_service
from ..schemas import ChatbotActivityResponse

router = APIRouter()


@router.get(path="/chatbot", response_model=Sequence[ChatbotActivityResponse])
async def list_chatbot_activity(
    service: Annotated[ChatbotActivityService, Depends(get_chatbot_activity_service)],
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=0, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[ChatbotActivityResponse]:
    """Lists chatbot activity audit records for the current admin's organization."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Solo los administradores pueden consultar la auditoria de chatbot")

    records = await service.list_by_organization(organization_id=current_user.organization_id, limit=limit, offset=offset)
    return [
        ChatbotActivityResponse(
            id=record.id or 0,
            organization_id=record.organization_id,
            actor_user_id=record.actor_user_id,
            actor_name=record.actor_name,
            actor_role=record.actor_role,
            action=record.action,
            conversation_title=conversation_title,
            created_at=record.created_at,
        )
        for record, conversation_title in records
    ]
