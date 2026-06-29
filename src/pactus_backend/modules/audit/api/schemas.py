"""HTTP schemas for audit APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ....modules.audit.domain.value_objs import (
    AITokenSource,
    AuditChatbotAction,
    AuditContractAction,
    AuditTemplateAction,
    AuditUserAction,
)


class ChatbotActivityResponse(BaseModel):
    """Response model for chatbot activity audit entries."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    actor_user_id: int
    actor_name: str | None
    actor_role: str
    action: AuditChatbotAction
    conversation_title: str | None
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


class TemplateActivityResponse(BaseModel):
    """Response model for template activity audit entries."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    actor_user_id: int
    actor_name: str | None
    actor_role: str
    action: AuditTemplateAction
    template_id: int | None
    template_format_id: int | None
    template_name: str | None
    document_type: str | None
    previous_state: str | None
    state: str | None
    created_at: datetime


class ContractActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    actor_user_id: int
    actor_name: str | None
    actor_role: str
    action: AuditContractAction
    document_id: int | None
    company_contract_id: int | None
    labor_contract_id: int | None
    document_name: str | None
    document_type: str | None
    previous_state: str | None
    state: str | None
    created_at: datetime


class AITokenUsageResponse(BaseModel):
    """Response model for individual AI token usage audit entries."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    actor_user_id: int
    source: AITokenSource
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    input_cost_usd: float | None
    output_cost_usd: float | None
    total_cost_usd: float | None
    model_used: str | None
    created_at: datetime


class AITokenUsageSummaryResponse(BaseModel):
    """Response model for aggregated AI token usage stats."""

    total_tokens: int
    total_cost_usd: float
    input_tokens: int
    output_tokens: int


__all__ = [
    "AITokenUsageResponse",
    "AITokenUsageSummaryResponse",
    "ChatbotActivityResponse",
    "ContractActivityResponse",
    "TemplateActivityResponse",
    "UserActivityResponse",
]
