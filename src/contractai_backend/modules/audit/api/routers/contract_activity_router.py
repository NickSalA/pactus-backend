"""Router for contract activity audit queries."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from contractai_backend.core.exceptions.base import ForbiddenError
from contractai_backend.modules.audit.api.dependencies import get_contract_activity_service
from contractai_backend.modules.audit.api.schemas import ContractActivityResponse
from contractai_backend.modules.audit.application.services import ContractActivityService
from contractai_backend.modules.users.domain.value_objs import UserRole
from contractai_backend.shared.api.dependencies.security import CurrentUserDep

router = APIRouter()


@router.get(path="/contracts", response_model=Sequence[ContractActivityResponse])
async def list_contract_activity(
    service: Annotated[ContractActivityService, Depends(get_contract_activity_service)],
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=0, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[ContractActivityResponse]:
    """Lists contract activity audit records for the current admin's organization."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Solo los administradores pueden consultar la auditoria de contratos")

    records = await service.list_by_organization(organization_id=current_user.organization_id, limit=limit, offset=offset)
    return [ContractActivityResponse.model_validate(record) for record in records]
