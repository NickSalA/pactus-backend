"""Routers for organization and membership management."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, status

from contractai_backend.modules.organizations.api.dependencies import get_organization_member_service
from contractai_backend.modules.organizations.api.schemas import (
    OrganizationMemberCreateRequest,
    OrganizationMemberResponse,
    OrganizationMemberRoleUpdateRequest,
)
from contractai_backend.modules.organizations.application.services import OrganizationMemberService
from contractai_backend.shared.api.dependencies.security import CurrentUserDep

router = APIRouter()


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
