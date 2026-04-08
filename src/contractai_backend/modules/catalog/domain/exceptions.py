"""Custom exceptions for the service catalog module."""

from ....core.exceptions.base import InternalServerError, ServiceUnavailableError


class ServiceDatabaseUnavailableError(ServiceUnavailableError):
    """Raised when the database is unreachable for service operations."""

    def __init__(self, message: str = "El servicio de base de datos para el catálogo no está disponible."):
        super().__init__(message)


class ServiceDatabaseError(InternalServerError):
    """Raised when an unexpected database error occurs during service operations."""

    def __init__(self, message: str = "Error inesperado en la base de datos del catálogo de servicios."):
        super().__init__(message)
