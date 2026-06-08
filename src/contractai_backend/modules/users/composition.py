"""Composition helpers for the users module."""

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.audit.application.services import UserActivityService
from contractai_backend.modules.audit.infrastructure import SQLModelUserActivityRepository

from .application.repositories.token_service import IAuthRepository
from .application.repositories.user_repo import IUserRepository
from .application.services.auth_service import AuthService
from .application.services.user_service import UserService
from .infrastructure.jwt_service import SupabaseAuthService
from .infrastructure.postgres_repo import SQLModelUserRepository


def build_auth_service(identity_provider: IAuthRepository, user_repository: IUserRepository) -> AuthService:
    """Builds the authentication application service."""
    return AuthService(jwt_service=identity_provider, repo=user_repository)


def build_user_service(user_repository: IUserRepository, user_activity_service: UserActivityService | None = None) -> UserService:
    """Builds the user application service."""
    return UserService(repo=user_repository, user_activity_service=user_activity_service)


def build_default_auth_service(*, session: AsyncSession, http_client: httpx.AsyncClient) -> AuthService:
    """Builds the default production authentication service graph."""
    return build_auth_service(
        identity_provider=SupabaseAuthService(client=http_client),
        user_repository=SQLModelUserRepository(session=session),
    )


def build_default_user_service(*, session: AsyncSession) -> UserService:
    """Builds the default production user service graph."""
    return build_user_service(
        user_repository=SQLModelUserRepository(session=session),
        user_activity_service=UserActivityService(repository=SQLModelUserActivityRepository(session=session)),
    )
