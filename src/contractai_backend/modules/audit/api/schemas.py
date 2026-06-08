"""HTTP schemas for audit APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from contractai_backend.modules.audit.domain.value_objs import AuditUserAction


class UserActivityResponse(BaseModel):
    """Response model for user activity audit entries."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    actor_user_id: int
    actor_name: str | None
    actor_role: str
    action: AuditUserAction
    target_user_id: int | None
    target_user_email: str | None
    target_user_name: str | None
    previous_role: str | None
    role: str | None
    created_at: datetime


__all__ = ["UserActivityResponse"]
