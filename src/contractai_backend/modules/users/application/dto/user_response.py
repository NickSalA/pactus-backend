"""Application DTOs for user read models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ...domain.entities import UserRole


class UserResponse(BaseModel):
    """User read model shared by application-facing modules."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    supabase_user_id: UUID | None
    email: str
    full_name: str | None
    avatar_url: str | None
    role: UserRole
    receives_notifications: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CurrentUserResponse(UserResponse):
    """Authenticated user read model."""

    subscription_active: bool
