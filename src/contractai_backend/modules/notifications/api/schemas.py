"""Schemas de request/response para el módulo de notificaciones."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contractai_backend.modules.notifications.domain.value_objs import NotificationType


class NotificationResponse(BaseModel):
    """Notificación derivada desde reglas activas y contratos próximos a vencer.

    El frontend gestiona el estado 'leída/descartada' via localStorage
    usando el campo `id` como clave estable entre sesiones.
    """

    id: str  # "contract-{doc_id}-{days}" — estable para localStorage
    document_id: int
    type: NotificationType
    title: str
    description: str
    days_remaining: int


class NotificationRuleCreateRequest(BaseModel):
    """Payload para crear reglas de notificación."""

    document_id: int | None = Field(default=None, gt=0)
    days_before_due: int = Field(..., gt=0)
    is_active: bool = True


class NotificationRuleUpdateRequest(BaseModel):
    """Payload para actualizar reglas de notificación."""

    days_before_due: int | None = Field(default=None, gt=0)
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_non_empty_patch(self) -> "NotificationRuleUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Patch request cannot be empty")
        return self


class NotificationRuleResponse(BaseModel):
    """Read model for notification rules."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    document_id: int | None = None
    days_before_due: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
