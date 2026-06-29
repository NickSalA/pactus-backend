"""Excepciones personalizadas para el módulo de plantillas."""

from ....core.exceptions.base import ForbiddenError, NotFoundError, UnprocessableEntityError, ValidationError


class TemplateNotFoundError(NotFoundError):
    """Se lanza cuando una plantilla no existe en la base de datos o no pertenece a la organización."""

    def __init__(self, message: str = "La plantilla solicitada no existe o no pertenece a la organización."):
        super().__init__(message=message)


class TemplateStateError(ValidationError):
    """Se lanza cuando se intenta realizar una operación inválida para el estado actual de la plantilla."""

    def __init__(self, message: str = "Operación no permitida para el estado actual de la plantilla."):
        super().__init__(message=message)


class TemplateAccessDeniedError(ForbiddenError):
    """Se lanza cuando un usuario no tiene permisos para acceder o gestionar una plantilla."""

    def __init__(self, message: str = "No tiene permisos para gestionar plantillas."):
        super().__init__(message=message)


class TemplateValidationError(ValidationError):
    """Se lanza cuando hay un error de validación en los datos de la plantilla."""

    def __init__(self, message: str = "Error de validación en la plantilla."):
        super().__init__(message=message)


class TemplateReferenceError(UnprocessableEntityError):
    """Se lanza cuando hay un problema con el archivo de referencia utilizado para generar una plantilla."""

    def __init__(self, message: str = "Error procesando el archivo de referencia."):
        super().__init__(message=message)
