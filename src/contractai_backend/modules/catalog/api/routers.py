"""API routers for the service catalog module."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from ....shared.api.dependencies.security import CurrentUserDep
from ...users.domain.value_objs import UserRole
from ..application.services import ServiceCatalogService
from .dependencies import get_service_catalog_service
from .schemas import ServiceCreateRequest, ServiceResponse, ServiceUpdateRequest

router = APIRouter()


@router.get(path="/", response_model=Sequence[ServiceResponse])
async def list_services(
    service: Annotated[ServiceCatalogService, Depends(get_service_catalog_service)],
    current_user: CurrentUserDep,
    include_inactive: bool = Query(default=False),
) -> Sequence[ServiceResponse]:
    """Endpoint to list available services for the current organization."""
    services = await service.list_services(
        organization_id=current_user.organization_id,
        include_inactive=include_inactive and current_user.role == UserRole.ADMIN,
    )
    return [ServiceResponse.model_validate(item) for item in services]


@router.post(path="/", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: ServiceCreateRequest,
    service: Annotated[ServiceCatalogService, Depends(get_service_catalog_service)],
    current_user: CurrentUserDep,
) -> ServiceResponse:
    """Endpoint to create a new catalog service."""
    item = await service.create_service(current_user=current_user, data=payload)
    return ServiceResponse.model_validate(item)


@router.patch(path="/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: int,
    payload: ServiceUpdateRequest,
    service: Annotated[ServiceCatalogService, Depends(get_service_catalog_service)],
    current_user: CurrentUserDep,
) -> ServiceResponse:
    """Endpoint to update a catalog service."""
    item = await service.update_service(current_user=current_user, service_id=service_id, data=payload)
    return ServiceResponse.model_validate(item)


@router.delete(path="/{service_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_service(
    service_id: int,
    service: Annotated[ServiceCatalogService, Depends(get_service_catalog_service)],
    current_user: CurrentUserDep,
) -> None:
    """Endpoint to delete a catalog service."""
    await service.delete_service(current_user=current_user, service_id=service_id)
