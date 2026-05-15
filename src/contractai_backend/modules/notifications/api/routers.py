"""HTTP endpoints for the notifications module."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from ....core.domain.access import ensure_admin
from ....shared.api.dependencies.security import CurrentUserDep
from ..application.services import EmailAlertService, NotificationRuleService
from .dependencies import get_email_alert_service, get_notification_rule_service
from .schemas import (
    NotificationResponse,
    NotificationRuleCreateRequest,
    NotificationRuleResponse,
    NotificationRuleUpdateRequest,
)

router = APIRouter()

EmailAlertServiceDep = Annotated[EmailAlertService, Depends(get_email_alert_service)]
NotificationRuleServiceDep = Annotated[NotificationRuleService, Depends(get_notification_rule_service)]


@router.get(path="/", response_model=list[NotificationResponse])
async def list_notifications(
    email_service: EmailAlertServiceDep,
    current_user: CurrentUserDep,
) -> list[NotificationResponse]:
    """Returns the contract alerts that apply to the authenticated user today."""
    if not current_user.is_active or not current_user.receives_notifications:
        return []

    events = await email_service.list_due_events_for_user(current_user=current_user)
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


@router.post(path="/send-email-alerts", status_code=200)
async def send_email_alerts(
    email_service: EmailAlertServiceDep,
    current_user: CurrentUserDep,
) -> dict:
    """Sends consolidated expiring-contract emails to subscribed users."""
    ensure_admin(current_user, "Solo los administradores pueden enviar alertas por correo")
    sent = await email_service.send_daily_alerts(
        organization_id=current_user.organization_id,
    )
    return {"emails_sent": sent}


@router.post(path="/cron/send-emails", status_code=200)
async def cron_send_emails(
    email_service: EmailAlertServiceDep,
) -> dict:
    """Cron endpoint: sends daily email alerts for all organizations.

    Called by the Vercel cron job via the Next.js proxy route /api/cron/send-emails.
    """
    result = await email_service.send_daily_alerts_cron()
    return result


@router.get(path="/rules", response_model=list[NotificationRuleResponse])
async def list_notification_rules(
    rule_service: NotificationRuleServiceDep,
    current_user: CurrentUserDep,
) -> list[NotificationRuleResponse]:
    """Lists notification rules for the current organization."""
    return await rule_service.list_rules(current_user=current_user)


@router.post(path="/rules", response_model=NotificationRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_notification_rule(
    payload: NotificationRuleCreateRequest,
    rule_service: NotificationRuleServiceDep,
    current_user: CurrentUserDep,
) -> NotificationRuleResponse:
    """Creates a notification rule for the current organization."""
    return await rule_service.create_rule(current_user=current_user, data=payload)


@router.patch(path="/rules/{rule_id}", response_model=NotificationRuleResponse)
async def update_notification_rule(
    rule_id: int,
    payload: NotificationRuleUpdateRequest,
    rule_service: NotificationRuleServiceDep,
    current_user: CurrentUserDep,
) -> NotificationRuleResponse:
    """Updates one notification rule for the current organization."""
    return await rule_service.update_rule(current_user=current_user, rule_id=rule_id, data=payload)


@router.delete(path="/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_notification_rule(
    rule_id: int,
    rule_service: NotificationRuleServiceDep,
    current_user: CurrentUserDep,
) -> None:
    """Deletes one notification rule for the current organization."""
    await rule_service.delete_rule(current_user=current_user, rule_id=rule_id)
