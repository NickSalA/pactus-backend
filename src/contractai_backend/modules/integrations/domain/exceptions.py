from contractai_backend.core.exceptions.base import AppError


class CloudStorageIntegrationError(AppError):
    def __init__(self, message: str = "Error al comunicarse con el proveedor de almacenamiento en la nube."):
        super().__init__(message=message, status_code=502)

class InvalidCloudTokenError(AppError):
    def __init__(self, message: str = "El token de acceso es inválido o ha expirado."):
        super().__init__(message=message, status_code=401)

class CloudFileNotFoundError(AppError):
    def __init__(self, message: str = "El archivo solicitado no se encontró en la nube."):
        super().__init__(message=message, status_code=404)
