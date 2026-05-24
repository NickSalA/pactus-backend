"""Routers for organization and membership management."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from contractai_backend.core.exceptions.base import ForbiddenError
from contractai_backend.modules.organizations.api.dependencies import (
    get_organization_member_service,
    get_organization_provisioning_service,
    get_organization_service,
)
from contractai_backend.modules.organizations.api.schemas import (
    OrganizationMemberCreateRequest,
    OrganizationMemberNotificationsUpdateRequest,
    OrganizationMemberResponse,
    OrganizationMemberRoleUpdateRequest,
    OrganizationProvisionRequest,
    OrganizationResponse,
    OrganizationUpdateRequest,
)
from contractai_backend.modules.organizations.application.services import (
    OrganizationMemberService,
    OrganizationProvisioningService,
    OrganizationService,
)
from contractai_backend.modules.users.domain.value_objs import UserRole
from contractai_backend.shared.api.dependencies.security import CurrentUserDep
from contractai_backend.shared.config import settings

router = APIRouter()


@router.get(path="", response_model=Sequence[OrganizationResponse])
async def list_organizations(
    service: Annotated[OrganizationService, Depends(get_organization_service)],
    current_user: CurrentUserDep,
    is_active: bool | None = None,
    name: str | None = None,
    ruc: str | None = None,
    limit: Annotated[int, Query(ge=0, le=settings.MAX_ORGANIZATIONS_LIMIT)] = settings.MAX_ORGANIZATIONS_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[OrganizationResponse]:
    """Lists organizations according to the current user's scope."""
    if current_user.role == UserRole.ADMIN:
        organization = await service.get_organization(current_user.organization_id)
        return [OrganizationResponse.model_validate(organization)]

    if current_user.role != UserRole.SUPERADMIN:
        raise ForbiddenError("Acceso denegado")

    organizations = await service.list_organizations(is_active=is_active, name=name, ruc=ruc, limit=limit, offset=offset)
    return [OrganizationResponse.model_validate(org) for org in organizations]


@router.post(path="", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationProvisionRequest,
    service: Annotated[OrganizationProvisioningService, Depends(get_organization_provisioning_service)],
    current_user: CurrentUserDep,
) -> OrganizationResponse:
    """Creates a new organization and its first admin. Only accessible by superadmins."""
    if current_user.role != UserRole.SUPERADMIN:
        raise ForbiddenError("Acceso denegado")
    organization = await service.provision_organization(payload)
    return OrganizationResponse.model_validate(organization)


@router.get(path="/me", response_model=OrganizationResponse)
async def get_my_organization(
    service: Annotated[OrganizationService, Depends(get_organization_service)],
    current_user: CurrentUserDep,
) -> OrganizationResponse:
    """Gets the current admin's organization."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Acceso denegado")
    organization = await service.get_organization(current_user.organization_id)
    return OrganizationResponse.model_validate(organization)


@router.patch(path="/me", response_model=OrganizationResponse)
async def update_my_organization(
    payload: OrganizationUpdateRequest,
    service: Annotated[OrganizationService, Depends(get_organization_service)],
    current_user: CurrentUserDep,
) -> OrganizationResponse:
    """Updates the current admin's organization."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Acceso denegado")
    organization = await service.update_organization(current_user.organization_id, payload)
    return OrganizationResponse.model_validate(organization)


@router.get(path="/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: int,
    service: Annotated[OrganizationService, Depends(get_organization_service)],
    current_user: CurrentUserDep,
) -> OrganizationResponse:
    """Gets an organization by ID."""
    if current_user.role != UserRole.SUPERADMIN and current_user.organization_id != organization_id:
        raise ForbiddenError("Acceso denegado")
    organization = await service.get_organization(organization_id)
    return OrganizationResponse.model_validate(organization)


@router.patch(path="/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: int,
    payload: OrganizationUpdateRequest,
    service: Annotated[OrganizationService, Depends(get_organization_service)],
    current_user: CurrentUserDep,
) -> OrganizationResponse:
    """Updates an organization within the current user's scope."""
    if current_user.role != UserRole.SUPERADMIN and current_user.organization_id != organization_id:
        raise ForbiddenError("Acceso denegado")
    organization = await service.update_organization(organization_id, payload)
    return OrganizationResponse.model_validate(organization)


@router.delete(path="/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    organization_id: int,
    service: Annotated[OrganizationService, Depends(get_organization_service)],
    current_user: CurrentUserDep,
) -> None:
    """Deletes an organization. Only accessible by superadmins."""
    if current_user.role != UserRole.SUPERADMIN:
        raise ForbiddenError("Acceso denegado")
    await service.delete_organization(organization_id)


@router.get(path="/me/members", response_model=Sequence[OrganizationMemberResponse])
async def list_members(
    service: Annotated[OrganizationMemberService, Depends(get_organization_member_service)],
    current_user: CurrentUserDep,
) -> Sequence[OrganizationMemberResponse]:
    """Lists the members that belong to the current user's organization."""
    members = await service.list_members(current_user)
    return [OrganizationMemberResponse.model_validate(member) for member in members]


@router.post(path="/me/members", response_model=OrganizationMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    payload: OrganizationMemberCreateRequest,
    service: Annotated[OrganizationMemberService, Depends(get_organization_member_service)],
    current_user: CurrentUserDep,
) -> OrganizationMemberResponse:
    """Creates a new member for the current user's organization."""
    member = await service.add_member(current_user=current_user, email=payload.email, role=payload.role)
    return OrganizationMemberResponse.model_validate(member)


@router.patch(path="/me/members/{member_id}/role", response_model=OrganizationMemberResponse)
async def update_member_role(
    member_id: int,
    payload: OrganizationMemberRoleUpdateRequest,
    service: Annotated[OrganizationMemberService, Depends(get_organization_member_service)],
    current_user: CurrentUserDep,
) -> OrganizationMemberResponse:
    """Updates the role of a member in the current user's organization."""
    member = await service.update_member_role(current_user=current_user, member_id=member_id, role=payload.role)
    return OrganizationMemberResponse.model_validate(member)


@router.patch(path="/me/members/{member_id}/notifications", response_model=OrganizationMemberResponse)
async def update_member_notifications(
    member_id: int,
    payload: OrganizationMemberNotificationsUpdateRequest,
    service: Annotated[OrganizationMemberService, Depends(get_organization_member_service)],
    current_user: CurrentUserDep,
) -> OrganizationMemberResponse:
    """Updates whether a member should receive expiration notifications."""
    member = await service.update_member_notifications(
        current_user=current_user,
        member_id=member_id,
        receives_notifications=payload.receives_notifications,
    )
    return OrganizationMemberResponse.model_validate(member)
