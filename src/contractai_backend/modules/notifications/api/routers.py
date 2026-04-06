"""HTTP endpoints for the notifications module."""

from typing import Annotated

from fastapi import APIRouter, Depends

from contractai_backend.modules.notifications.api.dependencies import get_email_alert_service
from contractai_backend.modules.notifications.api.schemas import NotificationResponse
from contractai_backend.modules.notifications.application.services.email_alert_service import EmailAlertService
from contractai_backend.shared.api.dependencies.security import CurrentUserDep

router = APIRouter()

EmailAlertServiceDep = Annotated[EmailAlertService, Depends(get_email_alert_service)]


@router.get(path="/", response_model=list[NotificationResponse])
async def list_notifications(
    email_service: EmailAlertServiceDep,
    current_user: CurrentUserDep,
) -> list[NotificationResponse]:
    """Returns the contract alerts that apply to the authenticated user today."""
    if not current_user.is_active or not current_user.receives_notifications:
        return []

    events = await email_service.list_due_events(organization_id=current_user.organization_id)
    return [
        NotificationResponse(
            id=f"contract-{event.document.id}-{event.days_remaining}",
            document_id=event.document.id,
            type=event.notification_type,
            title=f"Contrato por vencer en {event.days_remaining} días: {event.document.name}",
            description=f"El contrato con {event.document.client} vence el {event.document.end_date.strftime('%d/%m/%Y')}.",
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
    sent = await email_service.send_daily_alerts(
        organization_id=current_user.organization_id,
    )
    return {"emails_sent": sent}
