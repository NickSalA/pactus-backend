"""Custom exceptions for the dashboard module."""

from ....core.exceptions.base import ForbiddenError, InternalServerError, ServiceUnavailableError


class DashboardDatabaseUnavailableError(ServiceUnavailableError):
    """Raised when the database is unreachable for dashboard operations."""

    def __init__(self, message: str = "El servicio de base de datos para el dashboard no está disponible."):
        super().__init__(message)


class DashboardDatabaseError(InternalServerError):
    """Raised when an unexpected database error occurs during dashboard operations."""

    def __init__(self, message: str = "Error inesperado en la base de datos del dashboard."):
        super().__init__(message)


class DashboardForbiddenError(ForbiddenError):
    """Raised when the user lacks the necessary permissions to access dashboard functionality."""

    def __init__(self, message: str = "No tienes permisos para acceder a este dashboard."):
        super().__init__(message)
