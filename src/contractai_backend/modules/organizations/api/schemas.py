"""API schemas for organizations."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from contractai_backend.modules.users.api.schemas import UserResponse
from contractai_backend.modules.users.domain.value_objs import UserRole


class OrganizationResponse(BaseModel):
    """Read model for organization responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OrganizationMemberCreateRequest(BaseModel):
    email: str
    role: UserRole


class OrganizationMemberRoleUpdateRequest(BaseModel):
    role: UserRole


class OrganizationMemberNotificationsUpdateRequest(BaseModel):
    receives_notifications: bool


class OrganizationMemberResponse(UserResponse):
    pass
