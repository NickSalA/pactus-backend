"""Schemas de request/response para el módulo de notificaciones."""

from pydantic import BaseModel

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
