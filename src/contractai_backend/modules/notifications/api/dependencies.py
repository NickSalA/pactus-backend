"""Proveedores de dependencias para el módulo de notificaciones."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ..application.repositories import NotificationRuleRepository
from ..application.services import EmailAlertService, NotificationRuleService
from ..infrastructure import SQLModelNotificationRuleRepository
from ....shared.infrastructure.database import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _get_notification_rule_repository(session: SessionDep) -> SQLModelNotificationRuleRepository:
    """Construye el repositorio SQL de reglas de notificación."""
    return SQLModelNotificationRuleRepository(session=session)


NotificationRuleRepoDep = Annotated[NotificationRuleRepository, Depends(_get_notification_rule_repository)]


async def get_email_alert_service(
    session: SessionDep,
) -> EmailAlertService:
    """Provee el servicio de alertas por correo electrónico."""
    return EmailAlertService(session=session)


async def get_notification_rule_service(
    rule_repo: NotificationRuleRepoDep,
) -> NotificationRuleService:
    """Provee el servicio CRUD de reglas de notificación."""
    return NotificationRuleService(rule_repo=rule_repo)
