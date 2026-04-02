"""Tests unitarios para GmailService."""

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from contractai_backend.core.exceptions.base import BadGatewayError


def _make_service() -> "GmailService":
    from contractai_backend.modules.notifications.infrastructure.gmail_service import GmailService
    with patch("contractai_backend.modules.notifications.infrastructure.gmail_service.settings") as s:
        s.GMAIL_SENDER = "sender@gmail.com"
        s.GMAIL_APP_PASSWORD = "app-password"
        svc = GmailService()
    return svc


class TestGmailService:
    def test_raises_validation_error_when_no_credentials(self):
        from contractai_backend.core.exceptions.base import ValidationError
        from contractai_backend.modules.notifications.infrastructure.gmail_service import GmailService
        with patch("contractai_backend.modules.notifications.infrastructure.gmail_service.settings") as s:
            s.GMAIL_SENDER = ""
            s.GMAIL_APP_PASSWORD = ""
            with pytest.raises(ValidationError):
                GmailService()

    @pytest.mark.asyncio
    async def test_send_email_calls_send_sync(self):
        svc = _make_service()
        with patch.object(svc, "_send_sync") as mock_send:
            await svc.send_email("to@example.com", "Subject", "<p>Body</p>")
            mock_send.assert_called_once_with("to@example.com", "Subject", "<p>Body</p>")

    def test_send_sync_auth_error_raises_bad_gateway(self):
        svc = _make_service()
        with patch("smtplib.SMTP_SSL") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")

            with pytest.raises(BadGatewayError, match="Credenciales"):
                svc._send_sync("to@example.com", "Subject", "<p>Body</p>")

    def test_send_sync_smtp_error_raises_bad_gateway(self):
        svc = _make_service()
        with patch("smtplib.SMTP_SSL") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            mock_server.login.return_value = None
            mock_server.send_message.side_effect = smtplib.SMTPException("smtp error")

            with pytest.raises(BadGatewayError):
                svc._send_sync("to@example.com", "Subject", "<p>Body</p>")
