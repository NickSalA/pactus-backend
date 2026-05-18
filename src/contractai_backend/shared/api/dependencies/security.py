"""Dependencias de seguridad para la API."""

from typing import Annotated, Any

import httpx
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ....modules.users.application.services.auth_service import AuthService
from ....modules.users.composition import build_default_auth_service
from ....modules.users.domain.entities import UserTable
from ...infrastructure.database import get_session
from ...infrastructure.http import get_http_client
from .bearer import get_token


def get_auth_application_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> AuthService:
    """Builds the auth service used by global security dependencies."""
    return build_default_auth_service(session=session, http_client=client)


async def get_current_user(
    token: Annotated[str, Depends(get_token)],
    auth_service: Annotated[Any, Depends(get_auth_application_service)],
) -> UserTable:
    """Dependencia de seguridad global.

    Valida el token con Supabase y sincroniza/registra al usuario en la DB.
    """
    return await auth_service.authenticate_user(token)


CurrentUserDep = Annotated[UserTable, Depends(get_current_user)]
