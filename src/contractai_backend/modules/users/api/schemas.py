from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from contractai_backend.modules.users.domain.entities import UserRole


class UserResponse(BaseModel):
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
    pass
