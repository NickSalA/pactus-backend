"""Servicio de autenticación que obtiene los datos del usuario autenticado a partir del token de acceso."""

from datetime import UTC, datetime

from .....core.exceptions.base import ForbiddenError
from .....modules.users.application.dto.auth_dto import ExternalUserDTO
from ...domain.entities import UserTable
from ..repositories.token_service import IAuthRepository
from ..repositories.user_repo import IUserRepository


class AuthService:
    def __init__(self, jwt_service: IAuthRepository, repo: IUserRepository):
        self.jwt_service: IAuthRepository = jwt_service
        self.repo: IUserRepository = repo

    async def authenticate_user(self, access_token: str) -> UserTable:
        """Valida el token, sincroniza metadatos y devuelve el usuario de la DB."""
        auth_user: ExternalUserDTO = await self.jwt_service.get_authenticated_user(access_token)

        user: UserTable | None = await self.repo.get_by_email(email=auth_user.email)
        if user is None:
            raise ForbiddenError("El usuario no fue registrado por un administrador de organización")
        if not user.is_active:
            raise ForbiddenError("Acceso denegado para este usuario")

        needs_update = False

        if user.supabase_user_id is None:
            user.supabase_user_id = auth_user.id
            needs_update = True

        if auth_user.full_name and user.full_name != auth_user.full_name:
            user.full_name = auth_user.full_name
            needs_update = True

        if auth_user.avatar_url is not None and auth_user.avatar_url != user.avatar_url:
            user.avatar_url = auth_user.avatar_url
            needs_update = True

        if needs_update:
            user.updated_at: datetime = datetime.now(tz=UTC)
            user: UserTable = await self.repo.update(entity=user)

        return user
