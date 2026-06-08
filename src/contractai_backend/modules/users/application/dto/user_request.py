"""Application DTOs for user request models."""

from pydantic import BaseModel, ConfigDict

from ...domain.entities import UserRole


class UserUpdateRequest(BaseModel):
    """User update request model."""

    model_config = ConfigDict(from_attributes=True)

    full_name: str | None = None
    avatar_url: str | None = None
    role: UserRole | None = None
    receives_notifications: bool | None = None
    is_active: bool | None = None
