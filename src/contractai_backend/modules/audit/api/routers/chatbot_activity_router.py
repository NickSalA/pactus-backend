"""Router for chatbot activity audit queries."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from contractai_backend.core.exceptions.base import ForbiddenError
from contractai_backend.modules.audit.api.dependencies import get_chatbot_activity_service
from contractai_backend.modules.audit.api.schemas import ChatbotActivityResponse
from contractai_backend.modules.audit.application.services import ChatbotActivityService
from contractai_backend.modules.users.domain.value_objs import UserRole
from contractai_backend.shared.api.dependencies.security import CurrentUserDep

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
    return [ChatbotActivityResponse.model_validate(record) for record in records]
