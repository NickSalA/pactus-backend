"""HTTP schemas for audit APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from contractai_backend.modules.audit.domain.value_objs import AuditChatbotAction, AuditContractAction, AuditTemplateAction, AuditUserAction


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


__all__ = ["ChatbotActivityResponse", "ContractActivityResponse", "TemplateActivityResponse", "UserActivityResponse"]
