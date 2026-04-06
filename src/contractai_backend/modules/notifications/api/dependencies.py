"""Proveedores de dependencias para el módulo de notificaciones."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.notifications.application.services.email_alert_service import EmailAlertService
from contractai_backend.shared.infrastructure.database import get_session


async def get_email_alert_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EmailAlertService:
    """Provee el servicio de alertas por correo electrónico."""
    return EmailAlertService(session=session)
