from ....core.exceptions.base import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


class InvalidIntegrationPayloadError(ValidationError):
    def __init__(self, message: str = "El payload de integración es inválido."):
        super().__init__(message=message)


class CloudStorageIntegrationError(AppError):
    def __init__(self, message: str = "Error al comunicarse con el proveedor de almacenamiento en la nube."):
        super().__init__(message=message, status_code=502)


class InvalidCloudTokenError(AppError):
    def __init__(self, message: str = "El token de acceso es inválido o ha expirado."):
        super().__init__(message=message, status_code=401)


class CloudFileNotFoundError(AppError):
    def __init__(self, message: str = "El archivo solicitado no se encontró en la nube."):
        super().__init__(message=message, status_code=404)


class DuplicateJobError(ConflictError):
    def __init__(self, message: str = "Ya existe una importación en progreso. Espere a que termine."):
        super().__init__(message=message)


class JobNotFoundError(NotFoundError):
    def __init__(self, message: str = "Trabajo no encontrado."):
        super().__init__(message=message)


class JobAccessDeniedError(ForbiddenError):
    def __init__(self, message: str = "No tiene acceso a este trabajo."):
        super().__init__(message=message)
