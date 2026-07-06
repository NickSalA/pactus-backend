"""Módulo de repositorios para la gestión de usuarios."""

from abc import abstractmethod

from .....core.application.base import BaseRepository
from ...domain.entities import UserTable


class IUserRepository(BaseRepository[UserTable]):
    @abstractmethod
    async def get_by_email(self, email: str) -> UserTable | None:
        """Obtiene un usuario por su email. Devuelve None si no se encuentra."""
        pass
