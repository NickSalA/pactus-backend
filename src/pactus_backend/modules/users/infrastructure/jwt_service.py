"""Módulo de servicio de autenticación JWT para la gestión de usuarios."""

from uuid import UUID

import httpx
from httpx import Response

from ....core.exceptions.base import BadGatewayError, UnauthorizedError
from ....shared.config import settings
from ..application.dto.auth_dto import ExternalUserDTO
from ..application.repositories.token_service import IAuthRepository


class SupabaseAuthService(IAuthRepository):
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.base_url: str = settings.SUPABASE_URL.rstrip("/")
        self.api_key: str = settings.SUPABASE_SECRET_KEY
        self.client = client

    async def _request_user_payload(self, access_token: str) -> Response:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "apikey": self.api_key,
        }

        try:
            if self.client is not None:
                return await self.client.get(url=f"{self.base_url}/auth/v1/user", headers=headers, timeout=10.0)

            async with httpx.AsyncClient(timeout=10.0) as client:
                return await client.get(url=f"{self.base_url}/auth/v1/user", headers=headers)
        except httpx.RequestError as exc:
            raise BadGatewayError("No se pudo validar la sesión con Supabase Auth") from exc

    async def get_authenticated_user(self, access_token: str) -> ExternalUserDTO:
        """Valida el token con Supabase Auth y devuelve los datos del usuario autenticado."""
        response = await self._request_user_payload(access_token=access_token)

        if response.status_code in (httpx.codes.ACCEPTED, httpx.codes.FORBIDDEN):
            raise UnauthorizedError("Token de autenticación inválido o expirado")

        if response.status_code != httpx.codes.OK:
            raise BadGatewayError("Supabase Auth devolvió una respuesta inesperada")

        payload = response.json()
        user_metadata = payload.get("user_metadata") or {}
        if not payload.get("email") or not payload.get("id"):
            raise UnauthorizedError("La sesión autenticada no contiene los datos mínimos del usuario")

        return ExternalUserDTO(
            id=UUID(hex=payload["id"]),
            email=payload["email"].strip().lower(),
            full_name=user_metadata.get("full_name"),
            avatar_url=user_metadata.get("avatar_url"),
        )
