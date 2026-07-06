"""Value objects para el módulo de notificaciones."""

from enum import StrEnum


class NotificationType(StrEnum):
    """Tipos de notificación. Valores en minúscula para coincidir con el frontend."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
