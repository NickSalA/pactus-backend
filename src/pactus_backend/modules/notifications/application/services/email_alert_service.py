"""Notification service for expiring contracts and alert emails."""

from datetime import date

from loguru import logger

from .....modules.notifications.application.dto import NotificationEvent, NotificationRecipient
from .....modules.notifications.application.repositories import EmailSender, NotificationAlertRepository
from .....modules.notifications.domain import NotificationType
from .notification_email_renderer import NotificationEmailRenderer

DEFAULT_NOTIFICATION_DAYS = (15, 7, 3)
CRITICAL_ALERT_DAYS = 3
WARNING_ALERT_DAYS = 7


class EmailAlertService:
    def __init__(self, alert_repo: NotificationAlertRepository, email_sender: EmailSender):
        self.alert_repo = alert_repo
        self.email_sender = email_sender
        self.email_renderer = NotificationEmailRenderer()

    @staticmethod
    def _resolve_notification_type(days_remaining: int) -> NotificationType:
        if days_remaining <= CRITICAL_ALERT_DAYS:
            return NotificationType.CRITICAL
        if days_remaining <= WARNING_ALERT_DAYS:
            return NotificationType.WARNING
        return NotificationType.INFO

    @staticmethod
    def _filter_events_for_user(events: list[NotificationEvent], user: NotificationRecipient) -> list[NotificationEvent]:
        if not user.is_active or not user.receives_notifications:
            return []

        return events

    async def list_due_events(self, organization_id: int) -> list[NotificationEvent]:
        """Returns the alerts that should trigger today for one organization."""
        await self.alert_repo.sync_document_states(organization_id=organization_id)

        today = date.today()
        documents = await self.alert_repo.get_documents_for_notification_evaluation(organization_id=organization_id, today=today)
        rules_by_document, organization_default_days = await self.alert_repo.get_active_rule_map(organization_id=organization_id)

        events: list[NotificationEvent] = []
        for document in documents:
            if document.id is None:
                continue
            effective_days = rules_by_document.get(document.id) or organization_default_days or list(DEFAULT_NOTIFICATION_DAYS)
            days_remaining = (document.end_date - today).days
            if days_remaining not in effective_days:
                continue

            events.append(
                NotificationEvent(
                    document=document,
                    days_remaining=days_remaining,
                    notification_type=self._resolve_notification_type(days_remaining=days_remaining),
                )
            )

        return sorted(events, key=lambda event: (event.days_remaining, event.document.end_date, event.document.id or 0))

    async def list_due_events_for_user(self, current_user: NotificationRecipient) -> list[NotificationEvent]:
        """Returns only the alerts visible to one authenticated user."""
        events = await self.list_due_events(organization_id=current_user.organization_id)
        return self._filter_events_for_user(events=events, user=current_user)

    async def send_daily_alerts(self, organization_id: int) -> int:
        """Sends one consolidated expiring-contract email per subscribed user."""
        events = await self.list_due_events(organization_id=organization_id)
        if not events:
            logger.info("Sin alertas de contratos para org {}. No se envían correos.", organization_id)
            return 0

        recipients = await self.alert_repo.get_notification_recipients(organization_id=organization_id)
        if not recipients:
            logger.info("Sin usuarios suscritos a notificaciones para org {}.", organization_id)
            return 0

        sent_date = date.today()

        sent = 0
        for recipient in recipients:
            recipient_events = self._filter_events_for_user(events=events, user=recipient)
            if not recipient_events:
                continue

            subject, body = self.email_renderer.build_email(recipient=recipient, events=recipient_events, sent_date=sent_date)
            try:
                await self.email_sender.send_email(
                    to=recipient.email,
                    subject=subject,
                    html_body=body,
                )
                sent += 1
            except Exception as e:
                logger.error("No se pudo enviar correo a {}: {}", recipient.email, e)

        return sent

    async def send_daily_alerts_cron(self) -> dict[str, int]:
        """Sends daily email alerts for all active organizations.

        Iterates every organization that has at least one subscribed user and calls
        send_daily_alerts() for each. Records a send log entry so that re-runs on
        the same calendar day (UTC-5 / Lima) are safely skipped.
        """
        today = date.today()
        org_ids = await self.alert_repo.get_active_organization_ids()

        total_sent = 0
        orgs_processed = 0
        orgs_skipped = 0

        for org_id in org_ids:
            already_sent = await self.alert_repo.send_log_exists(organization_id=org_id, sent_date=today)
            if already_sent:
                logger.info("Org {} ya recibió correos hoy ({}). Saltando.", org_id, today)
                orgs_skipped += 1
                continue

            sent = await self.send_daily_alerts(organization_id=org_id)
            await self.alert_repo.record_send_log(organization_id=org_id, sent_date=today, emails_sent=sent)
            total_sent += sent
            orgs_processed += 1

        logger.info(
            "Cron finalizado: {} correos enviados, {} orgs procesadas, {} orgs saltadas.",
            total_sent, orgs_processed, orgs_skipped,
        )
        return {"emails_sent": total_sent, "orgs_processed": orgs_processed, "orgs_skipped": orgs_skipped}
