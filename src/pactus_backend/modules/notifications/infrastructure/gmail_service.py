"""Servicio de envío de correos usando Gmail SMTP (librería estándar de Python)."""

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from ....core.exceptions.base import BadGatewayError, ValidationError
from ....shared.config import settings

_GMAIL_HOST = "smtp.gmail.com"
_GMAIL_PORT = 465


class GmailService:
    """Envía correos HTML a través de Gmail SMTP con App Password.

    Usa asyncio.to_thread para no bloquear el event loop de FastAPI.
    """

    def __init__(self) -> None:
        if not settings.GMAIL_SENDER or not settings.GMAIL_APP_PASSWORD:
            raise ValidationError(
                "GMAIL_SENDER y GMAIL_APP_PASSWORD deben estar configurados en el .env"
            )
        self.sender = settings.GMAIL_SENDER
        self.password = settings.GMAIL_APP_PASSWORD

    async def send_email(self, to: str, subject: str, html_body: str) -> None:
        """Envía un correo HTML de forma asíncrona."""
        await asyncio.to_thread(self._send_sync, to, subject, html_body)

    def _send_sync(self, to: str, subject: str, html_body: str) -> None:
        """Envío sincrónico — se ejecuta en un thread separado."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"ContractAI <{self.sender}>"
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP_SSL(_GMAIL_HOST, _GMAIL_PORT) as server:
                server.login(self.sender, self.password)
                server.send_message(msg)
            logger.info("Correo enviado a {}", to)
        except smtplib.SMTPAuthenticationError as e:
            logger.error("Error de autenticación Gmail: {}", e)
            raise BadGatewayError("Credenciales de Gmail incorrectas. Verifica GMAIL_APP_PASSWORD.") from e
        except smtplib.SMTPException as e:
            logger.error("Error SMTP al enviar correo a {}: {}", to, e)
            raise BadGatewayError(f"Error al enviar correo a {to}.") from e
