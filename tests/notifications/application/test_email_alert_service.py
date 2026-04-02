"""Tests unitarios para EmailAlertService."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contractai_backend.modules.documents.domain import DocumentState, DocumentTable, DocumentType
from contractai_backend.modules.notifications.application.services.email_alert_service import EmailAlertService
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


def _make_doc(name: str = "Contrato", days_offset: int = 3) -> DocumentTable:
    today = date.today()
    return DocumentTable(
        id=1,
        organization_id=1,
        name=name,
        client="Cliente",
        type=DocumentType.LICENSES,
        start_date=today,
        end_date=today + timedelta(days=days_offset),
        state=DocumentState.ACTIVE,
    )


def _make_worker(email: str = "worker@example.com") -> UserTable:
    return UserTable(id=1, organization_id=1, email=email, role=UserRole.WORKER, is_active=True)


def _make_service(session=None, gmail=None) -> EmailAlertService:
    return EmailAlertService(session=session or AsyncMock(), gmail_service=gmail or AsyncMock())


class TestSendDailyAlerts:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_expiring_contracts(self):
        service = _make_service()
        with patch.object(service, "_get_expiring_documents", return_value=[]):
            with patch.object(service, "_get_worker_users", return_value=[]):
                result = await service.send_daily_alerts(organization_id=1)
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_workers(self):
        doc = _make_doc()
        service = _make_service()
        with patch.object(service, "_get_expiring_documents", return_value=[doc]):
            with patch.object(service, "_get_worker_users", return_value=[]):
                result = await service.send_daily_alerts(organization_id=1)
        assert result == 0

    @pytest.mark.asyncio
    async def test_sends_email_to_each_worker(self):
        doc = _make_doc()
        workers = [_make_worker("a@example.com"), _make_worker("b@example.com")]
        gmail = AsyncMock()

        service = _make_service(gmail=gmail)
        with patch.object(service, "_get_expiring_documents", return_value=[doc]):
            with patch.object(service, "_get_worker_users", return_value=workers):
                result = await service.send_daily_alerts(organization_id=1)

        assert result == 2
        assert gmail.send_email.call_count == 2

    @pytest.mark.asyncio
    async def test_continues_when_one_email_fails(self):
        doc = _make_doc()
        workers = [_make_worker("a@example.com"), _make_worker("b@example.com")]
        gmail = AsyncMock()
        gmail.send_email.side_effect = [Exception("smtp error"), None]

        service = _make_service(gmail=gmail)
        with patch.object(service, "_get_expiring_documents", return_value=[doc]):
            with patch.object(service, "_get_worker_users", return_value=workers):
                result = await service.send_daily_alerts(organization_id=1)

        assert result == 1  # solo el segundo tuvo éxito


class TestBuildSections:
    def test_returns_html_string(self):
        service = _make_service()
        doc = _make_doc()
        sections = service._build_sections({3: [doc]})
        assert isinstance(sections, str)
        assert "Contrato" in sections

    def test_empty_contracts_returns_empty_string(self):
        service = _make_service()
        sections = service._build_sections({})
        assert sections == ""


class TestBuildEmailHtml:
    def test_contains_name_and_total(self):
        service = _make_service()
        html = service._build_email_html(name="Juan", total=3, sections="<div>test</div>", date_str="01/01/2024")
        assert "Juan" in html
        assert "3" in html
        assert "01/01/2024" in html
