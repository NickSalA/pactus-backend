"""HTTP schemas for audit APIs."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from contractai_backend.modules.audit.domain.value_objs import AuditChatbotAction, AuditUserAction


class ChatbotActivityResponse(BaseModel):
    """Response model for chatbot activity audit entries."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    actor_user_id: int
    actor_name: str | None
    actor_role: str
    action: AuditChatbotAction
    conversation_id: int | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    input_cost_usd: Decimal | None
    output_cost_usd: Decimal | None
    total_cost_usd: Decimal | None
    model_used: str | None
    created_at: datetime


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


__all__ = ["ChatbotActivityResponse", "UserActivityResponse"]
