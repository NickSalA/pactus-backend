"""Módulo que define la clase base para las excepciones de negocio de ContractAI."""

from fastapi import status


class AppError(Exception):
    """Clase base para todas las excepciones de negocio de ContractAI."""

    def __init__(self, message: str, status_code: int = 400):
        self.message: str = message
        self.status_code: int = status_code

        super().__init__(self.message)


# 4XX - Errores de cliente (validación, autenticación, permisos)


class NotFoundError(AppError):
    """Excepción para recursos no encontrados (HTTP 404)."""

    def __init__(self, message: str = "Recurso no encontrado"):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class ValidationError(AppError):
    """Excepción para reglas de negocio violadas o datos inválidos (HTTP 400)."""

    def __init__(self, message: str = "Error de validación de datos"):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST)


class UnprocessableEntityError(AppError):
    """Excepción para errores semánticos o contenido que no puede ser procesado (HTTP 422)."""

    def __init__(self, message: str = "Entidad no procesable"):
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class UnauthorizedError(AppError):
    """Excepción para fallos de autenticación (HTTP 401)."""

    def __init__(self, message: str = "No autenticado"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppError):
    """Excepción para falta de permisos (HTTP 403)."""

    def __init__(self, message: str = "No tiene permisos para realizar esta acción"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class ConflictError(AppError):
    """Excepción para conflictos de estado, ej. registro duplicado (HTTP 409)."""

    def __init__(self, message: str = "Conflicto en el recurso"):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class TooManyRequestsError(AppError):
    """Excepción para cuotas de uso excedidas o límite de peticiones (HTTP 429)."""

    def __init__(self, message: str = "Demasiadas peticiones o cuota excedida"):
        super().__init__(message, status_code=status.HTTP_429_TOO_MANY_REQUESTS)


# 5XX - Errores de servidor (infraestructura o dependencias)


class InternalServerError(AppError):
    """Excepción para fallos de infraestructura o dependencias (HTTP 500)."""

    def __init__(self, message: str = "Error interno del servidor"):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BadGatewayError(AppError):
    """Excepción para fallos en dependencias externas (HTTP 502)."""

    def __init__(self, message: str = "Error en una dependencia externa"):
        super().__init__(message, status_code=status.HTTP_502_BAD_GATEWAY)


class ServiceUnavailableError(AppError):
    """Excepción para servicios o dependencias no disponibles (HTTP 503)."""

    def __init__(self, message: str = "Servicio no disponible"):
        super().__init__(message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class GatewayTimeoutError(AppError):
    """Excepción para tiempos de espera agotados en dependencias externas (HTTP 504)."""

    def __init__(self, message: str = "Tiempo de espera agotado al comunicarse con un servicio externo"):
        super().__init__(message, status_code=status.HTTP_504_GATEWAY_TIMEOUT)
