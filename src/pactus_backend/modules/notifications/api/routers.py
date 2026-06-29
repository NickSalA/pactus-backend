"""HTTP endpoints for the notifications module."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from ....core.domain.access import ensure_admin
from ....core.exceptions.base import ServiceUnavailableError, UnauthorizedError
from ....shared.api.dependencies.security import CurrentUserDep
from ....shared.config import settings
from ..application.dto import NotificationRecipient
from ..application.services import EmailAlertService, NotificationRuleService
from .dependencies import get_email_alert_service, get_notification_rule_service
from .schemas import (
    CronSendEmailsResponse,
    NotificationResponse,
    NotificationRuleCreateRequest,
    NotificationRuleResponse,
    NotificationRuleUpdateRequest,
    SendEmailAlertsResponse,
)

router = APIRouter()

EmailAlertServiceDep = Annotated[EmailAlertService, Depends(get_email_alert_service)]
NotificationRuleServiceDep = Annotated[NotificationRuleService, Depends(get_notification_rule_service)]
CronSecretHeader = Annotated[str | None, Header(alias="X-Cron-Secret")]


def validate_cron_secret(x_cron_secret: CronSecretHeader) -> None:
    """Validates cron requests without coupling the endpoint to JWT auth."""
    if settings.CRON_SECRET is None:
        raise ServiceUnavailableError("Cron secret is not configured")
    if x_cron_secret != settings.CRON_SECRET:
        raise UnauthorizedError("Invalid cron secret")


def _notification_recipient_from_current_user(current_user) -> NotificationRecipient:
    """Converts the authenticated DB user into the notification application read model."""
    return NotificationRecipient(
        id=current_user.id,
        organization_id=current_user.organization_id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        receives_notifications=current_user.receives_notifications,
    )


@router.get(path="/", response_model=list[NotificationResponse])
async def list_notifications(
    email_service: EmailAlertServiceDep,
    current_user: CurrentUserDep,
) -> list[NotificationResponse]:
    """Returns the contract alerts that apply to the authenticated user today."""
    if not current_user.is_active or not current_user.receives_notifications:
        return []

    events = await email_service.list_due_events_for_user(current_user=_notification_recipient_from_current_user(current_user))
    return [
        NotificationResponse(
            id=f"contract-{event.document.id}-{event.days_remaining}",
            document_id=event.document.id,
            type=event.notification_type,
            title=f"Contrato por vencer en {event.days_remaining} días: {event.document.file_name or 'Contrato sin archivo'}",
            description=f"El contrato vence el {event.document.end_date.strftime('%d/%m/%Y')}.",
            days_remaining=event.days_remaining,
        )
        for event in events
        if event.document.id is not None
    ]


@router.post(path="/send-email-alerts", response_model=SendEmailAlertsResponse, status_code=200)
async def send_email_alerts(
    email_service: EmailAlertServiceDep,
    current_user: CurrentUserDep,
) -> SendEmailAlertsResponse:
    """Sends consolidated expiring-contract emails to subscribed users."""
    ensure_admin(current_user, "Solo los administradores pueden enviar alertas por correo")
    sent = await email_service.send_daily_alerts(
        organization_id=current_user.organization_id,
    )
    return SendEmailAlertsResponse(emails_sent=sent)


@router.post(
    path="/cron/send-emails",
    response_model=CronSendEmailsResponse,
    responses={401: {"description": "Invalid cron secret"}, 503: {"description": "Cron secret is not configured"}},
    status_code=200,
)
async def cron_send_emails(
    email_service: EmailAlertServiceDep,
    _: Annotated[None, Depends(validate_cron_secret)],
) -> CronSendEmailsResponse:
    """Cron endpoint: sends daily email alerts for all organizations.

    Called by the Vercel cron job via the Next.js proxy route /api/cron/send-emails.
    """
    result = await email_service.send_daily_alerts_cron()
    return CronSendEmailsResponse(**result)


@router.get(path="/rules", response_model=list[NotificationRuleResponse])
async def list_notification_rules(
    rule_service: NotificationRuleServiceDep,
    current_user: CurrentUserDep,
) -> list[NotificationRuleResponse]:
    """Lists notification rules for the current organization."""
    rules = await rule_service.list_rules(current_user=current_user)
    return [NotificationRuleResponse.model_validate(rule) for rule in rules]


@router.post(path="/rules", response_model=NotificationRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_notification_rule(
    payload: NotificationRuleCreateRequest,
    rule_service: NotificationRuleServiceDep,
    current_user: CurrentUserDep,
) -> NotificationRuleResponse:
    """Creates a notification rule for the current organization."""
    rule = await rule_service.create_rule(current_user=current_user, data=payload)
    return NotificationRuleResponse.model_validate(rule)


@router.patch(path="/rules/{rule_id}", response_model=NotificationRuleResponse)
async def update_notification_rule(
    rule_id: int,
    payload: NotificationRuleUpdateRequest,
    rule_service: NotificationRuleServiceDep,
    current_user: CurrentUserDep,
) -> NotificationRuleResponse:
    """Updates one notification rule for the current organization."""
    rule = await rule_service.update_rule(current_user=current_user, rule_id=rule_id, data=payload)
    return NotificationRuleResponse.model_validate(rule)


@router.delete(path="/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_notification_rule(
    rule_id: int,
    rule_service: NotificationRuleServiceDep,
    current_user: CurrentUserDep,
) -> None:
    """Deletes one notification rule for the current organization."""
    await rule_service.delete_rule(current_user=current_user, rule_id=rule_id)
