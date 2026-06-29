"""Router for template activity audit queries."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from .....core.exceptions.base import ForbiddenError
from .....shared.api.dependencies.security import CurrentUserDep
from ....users.domain.value_objs import UserRole
from ...api.schemas import TemplateActivityResponse
from ...application.services import TemplateActivityService
from ..dependencies import get_template_activity_service

router = APIRouter()


@router.get(path="/templates", response_model=Sequence[TemplateActivityResponse])
async def list_template_activity(
    service: Annotated[TemplateActivityService, Depends(get_template_activity_service)],
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=0, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[TemplateActivityResponse]:
    """Lists template activity audit records for the current admin's organization."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Solo los administradores pueden consultar la auditoria de plantillas")

    records = await service.list_by_organization(organization_id=current_user.organization_id, limit=limit, offset=offset)
    return [TemplateActivityResponse.model_validate(record) for record in records]
