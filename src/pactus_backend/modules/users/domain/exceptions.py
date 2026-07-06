"""Excepciones de dominio específicas para el módulo de usuarios."""

from ....core.exceptions.base import NotFoundError


class UserNotFoundError(NotFoundError):
    """Excepción lanzada cuando un usuario no es encontrado."""

    def __init__(self, message: str = "Usuario no encontrado") -> None:
        super().__init__(message=message)
