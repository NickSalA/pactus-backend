"""Custom exceptions for the folders module."""

from ....core.exceptions.base import InternalServerError, NotFoundError, ServiceUnavailableError, ValidationError


class FolderNotFoundError(NotFoundError):
    """Raised when a folder does not exist."""

    def __init__(self, folder_id: int):
        super().__init__(message=f"La carpeta con ID {folder_id} no fue encontrada.")


class FolderValidationError(ValidationError):
    """Raised when folder data violates validation rules."""

    def __init__(self, message: str = "Los datos de la carpeta son inválidos."):
        super().__init__(message)


class FolderDatabaseUnavailableError(ServiceUnavailableError):
    """Raised when the database is unreachable for folder operations."""

    def __init__(self, message: str = "El servicio de base de datos para carpetas no está disponible."):
        super().__init__(message)


class FolderDatabaseError(InternalServerError):
    """Raised when an unexpected database error occurs during folder operations."""

    def __init__(self, message: str = "Error inesperado en la base de datos de carpetas."):
        super().__init__(message)
