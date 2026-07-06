"""Application DTOs for user request models."""

from pydantic import BaseModel, ConfigDict

from ...domain.entities import UserRole


class UserUpdateRequest(BaseModel):
    """User update request model."""

    model_config = ConfigDict(from_attributes=True)

    role: UserRole | None = None
