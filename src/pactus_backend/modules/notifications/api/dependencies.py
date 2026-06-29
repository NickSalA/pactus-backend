"""Proveedores de dependencias para el módulo de notificaciones."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ....shared.infrastructure.database import get_session
from ..application.repositories import NotificationAlertRepository, NotificationRuleRepository
from ..application.services import EmailAlertService, NotificationRuleService
from ..infrastructure import GmailService, SQLModelNotificationAlertRepository, SQLModelNotificationRuleRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _get_notification_rule_repository(session: SessionDep) -> SQLModelNotificationRuleRepository:
    """Construye el repositorio SQL de reglas de notificación."""
    return SQLModelNotificationRuleRepository(session=session)


async def _get_notification_alert_repository(session: SessionDep) -> SQLModelNotificationAlertRepository:
    """Builds the SQL repository for notification alert evaluation."""
    return SQLModelNotificationAlertRepository(session=session)


NotificationRuleRepoDep = Annotated[NotificationRuleRepository, Depends(_get_notification_rule_repository)]
NotificationAlertRepoDep = Annotated[NotificationAlertRepository, Depends(_get_notification_alert_repository)]


async def get_email_alert_service(
    alert_repo: NotificationAlertRepoDep,
) -> EmailAlertService:
    """Provee el servicio de alertas por correo electrónico."""
    return EmailAlertService(alert_repo=alert_repo, email_sender=GmailService())


async def get_notification_rule_service(
    rule_repo: NotificationRuleRepoDep,
) -> NotificationRuleService:
    """Provee el servicio CRUD de reglas de notificación."""
    return NotificationRuleService(rule_repo=rule_repo)
