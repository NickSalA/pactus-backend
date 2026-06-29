"""Dependencia para extraer el token Bearer del header de autorización."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ....core.exceptions.base import UnauthorizedError

_bearer = HTTPBearer(auto_error=False)

CredentialDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]

def get_token(credentials: CredentialDep) -> str:
    """Extrae el token del header 'Authorization: Bearer <token>'.

    Usar HTTPBearer (en lugar de Header genérico) registra el security scheme
    en OpenAPI, lo que hace funcionar el botón 'Authorize' en Swagger UI.
    """
    if not credentials:
        raise UnauthorizedError("No se proporcionó un token de autenticación")
    return credentials.credentials
