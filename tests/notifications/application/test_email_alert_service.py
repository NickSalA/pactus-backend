"""Tests unitarios para EmailAlertService."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from pactus_backend.modules.notifications.application.dto import NotificationDocument, NotificationEvent, NotificationRecipient
from pactus_backend.modules.notifications.application.services.email_alert_service import EmailAlertService
from pactus_backend.modules.notifications.domain.value_objs import NotificationType


def _make_doc(name: str = "Contrato", days_offset: int = 3) -> NotificationDocument:
    today = date.today()
    return NotificationDocument(
        id=1,
        type="COMPANY",
        end_date=today + timedelta(days=days_offset),
        file_name=name,
    )


def _make_worker(email: str = "worker@example.com") -> NotificationRecipient:
    return NotificationRecipient(
        id=1,
        organization_id=1,
        email=email,
        full_name="Worker Test",
        receives_notifications=True,
        is_active=True,
    )


def _make_service(alert_repo=None, email_sender=None) -> EmailAlertService:
    return EmailAlertService(alert_repo=alert_repo or AsyncMock(), email_sender=email_sender or AsyncMock())


class TestSendDailyAlerts:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_expiring_contracts(self):
        service = _make_service()
        with patch.object(service, "list_due_events", return_value=[]):
            result = await service.send_daily_alerts(organization_id=1)
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_recipients(self):
        doc = _make_doc()
        service = _make_service()
        with patch.object(
            service,
            "list_due_events",
            return_value=[NotificationEvent(document=doc, days_remaining=3, notification_type=NotificationType.CRITICAL)],
        ):
            service.alert_repo.get_notification_recipients.return_value = []
            result = await service.send_daily_alerts(organization_id=1)
        assert result == 0

    @pytest.mark.asyncio
    async def test_sends_email_to_each_worker(self):
        doc = _make_doc()
        workers = [_make_worker("a@example.com"), _make_worker("b@example.com")]
        email_sender = AsyncMock()

        service = _make_service(email_sender=email_sender)
        service.alert_repo.get_notification_recipients.return_value = workers
        with patch.object(
            service,
            "list_due_events",
            return_value=[NotificationEvent(document=doc, days_remaining=3, notification_type=NotificationType.CRITICAL)],
        ):
            result = await service.send_daily_alerts(organization_id=1)

        assert result == 2
        assert email_sender.send_email.call_count == 2

    @pytest.mark.asyncio
    async def test_continues_when_one_email_fails(self):
        doc = _make_doc()
        workers = [_make_worker("a@example.com"), _make_worker("b@example.com")]
        email_sender = AsyncMock()
        email_sender.send_email.side_effect = [Exception("smtp error"), None]

        service = _make_service(email_sender=email_sender)
        service.alert_repo.get_notification_recipients.return_value = workers
        with patch.object(
            service,
            "list_due_events",
            return_value=[NotificationEvent(document=doc, days_remaining=3, notification_type=NotificationType.CRITICAL)],
        ):
            result = await service.send_daily_alerts(organization_id=1)

        assert result == 1  # solo el segundo tuvo éxito


class TestDueEvents:
    @pytest.mark.asyncio
    async def test_list_due_events_uses_notification_dtos(self):
        today = date.today()
        alert_repo = AsyncMock()
        alert_repo.get_documents_for_notification_evaluation.return_value = [
            NotificationDocument(id=1, type="COMPANY", end_date=today + timedelta(days=7), file_name="Contrato A"),
            NotificationDocument(id=2, type="LABOR", end_date=today + timedelta(days=10), file_name="Contrato B"),
        ]
        alert_repo.get_active_rule_map.return_value = ({1: [7]}, [])
        service = _make_service(alert_repo=alert_repo)

        events = await service.list_due_events(organization_id=1)

        assert len(events) == 1
        assert events[0].document.id == 1
        assert events[0].notification_type == NotificationType.WARNING
        alert_repo.sync_document_states.assert_called_once_with(organization_id=1)
