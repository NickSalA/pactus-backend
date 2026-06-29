"""Módulo de repositorio de autenticación para la gestión de usuarios."""

from abc import ABC, abstractmethod

from ..dto.auth_dto import ExternalUserDTO


class IAuthRepository(ABC):
    @abstractmethod
    async def get_authenticated_user(self, access_token: str) -> ExternalUserDTO:
        """Valida el token y devuelve los datos del usuario externo."""
        pass
