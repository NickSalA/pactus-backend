"""Composition helpers for the users module."""

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from .application.repositories.token_service import IAuthRepository
from .application.repositories.user_repo import IUserRepository
from .application.services.auth_service import AuthService
from .infrastructure.jwt_service import SupabaseAuthService
from .infrastructure.postgres_repo import SQLModelUserRepository


def build_auth_service(identity_provider: IAuthRepository, user_repository: IUserRepository) -> AuthService:
    """Builds the authentication application service."""
    return AuthService(jwt_service=identity_provider, repo=user_repository)


def build_default_auth_service(*, session: AsyncSession, http_client: httpx.AsyncClient) -> AuthService:
    """Builds the default production authentication service graph."""
    return build_auth_service(
        identity_provider=SupabaseAuthService(client=http_client),
        user_repository=SQLModelUserRepository(session=session),
    )
