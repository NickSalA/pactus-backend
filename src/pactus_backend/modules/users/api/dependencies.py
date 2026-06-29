"""Módulo de Dependencias para el API de Usuarios."""

from typing import Annotated

import httpx
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ....shared.infrastructure.database import get_session
from ....shared.infrastructure.http import get_http_client
from ..application.repositories.token_service import IAuthRepository
from ..application.repositories.user_repo import IUserRepository
from ..application.services.auth_service import AuthService
from ..application.services.user_service import UserService
from ..composition import build_default_auth_service, build_default_user_service
from ..infrastructure.jwt_service import SupabaseAuthService
from ..infrastructure.postgres_repo import SQLModelUserRepository


async def get_user_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> IUserRepository:
    """Inyecta la implementación concreta del repositorio de usuarios."""
    return SQLModelUserRepository(session=session)


def get_identity_provider(client: Annotated[httpx.AsyncClient, Depends(get_http_client)]) -> IAuthRepository:
    """Inyecta el proveedor de identidad (Supabase)."""
    return SupabaseAuthService(client=client)


def get_auth_application_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> AuthService:
    """Inyecta el servicio de aplicación que orquesta la autenticación."""
    return build_default_auth_service(session=session, http_client=client)


def get_user_application_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserService:
    """Inyecta el servicio de aplicación de usuarios."""
    return build_default_user_service(session=session)
