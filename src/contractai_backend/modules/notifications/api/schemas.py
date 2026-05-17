"""Schemas de request/response para el módulo de notificaciones."""

from pydantic import BaseModel

from contractai_backend.modules.notifications.domain.value_objs import NotificationType

from ..application.dto import (
    CronSendEmailsResponse as ApplicationCronSendEmailsResponse,
)
from ..application.dto import (
    NotificationRuleCreateRequest as ApplicationNotificationRuleCreateRequest,
)
from ..application.dto import (
    NotificationRuleResponse as ApplicationNotificationRuleResponse,
)
from ..application.dto import (
    NotificationRuleUpdateRequest as ApplicationNotificationRuleUpdateRequest,
)
from ..application.dto import (
    SendEmailAlertsResponse as ApplicationSendEmailAlertsResponse,
)

__all__ = [
    "CronSendEmailsResponse",
    "NotificationResponse",
    "NotificationRuleCreateRequest",
    "NotificationRuleResponse",
    "NotificationRuleUpdateRequest",
    "SendEmailAlertsResponse",
]


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


class NotificationRuleCreateRequest(ApplicationNotificationRuleCreateRequest):
    """HTTP request body for creating notification rules."""


class NotificationRuleUpdateRequest(ApplicationNotificationRuleUpdateRequest):
    """HTTP request body for updating notification rules."""


class NotificationRuleResponse(ApplicationNotificationRuleResponse):
    """HTTP response body for notification rules."""


class SendEmailAlertsResponse(ApplicationSendEmailAlertsResponse):
    """HTTP response body for manual email sends."""


class CronSendEmailsResponse(ApplicationCronSendEmailsResponse):
    """HTTP response body for cron email sends."""
