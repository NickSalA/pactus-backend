"""Excepciones personalizadas para el módulo de notificaciones."""

from ....core.exceptions.base import InternalServerError, ServiceUnavailableError


class NotificationDatabaseUnavailableError(ServiceUnavailableError):
    """Se lanza cuando la base de datos relacional no está disponible para operaciones de notificaciones."""

    def __init__(self, message: str = "La base de datos relacional para notificaciones no está disponible."):
        super().__init__(message)


class NotificationDatabaseError(InternalServerError):
    """Se lanza cuando ocurre un error inesperado al acceder a la base de datos relacional para notificaciones."""

    def __init__(self, message: str = "Error al acceder a la base de datos relacional para notificaciones."):
        super().__init__(message)
