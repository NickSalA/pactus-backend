"""Excepciones personalizadas para el módulo de organizaciones."""

from ....core.exceptions.base import ConflictError, NotFoundError


class OrganizationNotFoundError(NotFoundError):
    """Se lanza cuando una organización no existe en la base de datos."""

    def __init__(self, message: str = "La organización solicitada no existe."):
        super().__init__(message=message)


class OrganizationAlreadyExistsError(ConflictError):
    """Se lanza cuando se intenta crear una organización o actualizar el nombre a uno que ya está en uso."""

    def __init__(self, message: str = "Ya existe una organización con ese nombre."):
        super().__init__(message=message)
