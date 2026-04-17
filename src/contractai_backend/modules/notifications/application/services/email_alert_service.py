"""Notification service for expiring contracts and alert emails."""

import html
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime

from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.core.exceptions.base import InternalServerError, ServiceUnavailableError
from contractai_backend.modules.documents.domain.access_policy import can_read_document_type
from contractai_backend.modules.documents.domain import DocumentTable
from contractai_backend.modules.documents.domain.value_objs import DocumentState, DocumentType
from contractai_backend.modules.notifications.domain import NotificationRuleTable, NotificationType
from contractai_backend.modules.notifications.domain.entities import NotificationSendLog
from contractai_backend.modules.notifications.infrastructure.gmail_service import GmailService
from contractai_backend.modules.users.domain.entities import UserTable

DEFAULT_NOTIFICATION_DAYS = (15, 7, 3)


@dataclass(frozen=True)
class NotificationEvent:
    """Represents a contract alert triggered for the current day."""

    document: DocumentTable
    days_remaining: int
    notification_type: NotificationType


class EmailAlertService:
    def __init__(self, session: AsyncSession, gmail_service: GmailService | None = None):
        self.session = session
        self.gmail_service = gmail_service

    @staticmethod
    def _read_scalar_result(value: object) -> int:
        if hasattr(value, "_mapping"):
            mapping = value._mapping
            if mapping:
                return int(next(iter(mapping.values())) or 0)

        if isinstance(value, tuple):
            return int((value[0] if value else 0) or 0)

        return int(value or 0)

    @staticmethod
    def _resolve_notification_type(days_remaining: int) -> NotificationType:
        if days_remaining <= 3:
            return NotificationType.CRITICAL
        if days_remaining <= 7:
            return NotificationType.WARNING
        return NotificationType.INFO

    @staticmethod
    def _resolve_threshold_styles(notification_type: NotificationType) -> tuple[str, str, str, str, str, str, str]:
        style_mapping = {
            NotificationType.CRITICAL: ("#EF4444", "#FEF2F2", "#FECACA", "#991B1B", "#B91C1C", "CRITICO", "[CRITICAL]"),
            NotificationType.WARNING: ("#F97316", "#FFF7ED", "#FED7AA", "#9A3412", "#C2410C", "ADVERTENCIA", "[WARNING]"),
            NotificationType.INFO: ("#3B82F6", "#EFF6FF", "#BFDBFE", "#1E40AF", "#1D4ED8", "AVISO", "[INFO]"),
        }
        return style_mapping[notification_type]

    @staticmethod
    def _filter_events_for_user(events: list[NotificationEvent], user: UserTable) -> list[NotificationEvent]:
        if not user.is_active or not user.receives_notifications:
            return []

        return [event for event in events if can_read_document_type(user.role, DocumentType(event.document.type))]

    async def sync_document_states(self, organization_id: int) -> int:
        """Updates persisted contract states using the DB synchronization function."""
        try:
            result = await self.session.exec(
                text("select public.sync_document_states(:organization_id)"),
                params={"organization_id": organization_id},
            )
            return self._read_scalar_result(result.one())
        except OperationalError as e:
            raise ServiceUnavailableError("La base de datos no está disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al sincronizar estados de contratos") from e

    async def list_due_events(self, organization_id: int) -> list[NotificationEvent]:
        """Returns the alerts that should trigger today for one organization."""
        await self.sync_document_states(organization_id=organization_id)

        today = date.today()
        documents = await self._get_documents_for_notification_evaluation(organization_id=organization_id, today=today)
        rules_by_document, organization_default_days = await self._get_active_rule_map(organization_id=organization_id)

        events: list[NotificationEvent] = []
        for document in documents:
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

    async def list_due_events_for_user(self, current_user: UserTable) -> list[NotificationEvent]:
        """Returns only the alerts visible to one authenticated user."""
        events = await self.list_due_events(organization_id=current_user.organization_id)
        return self._filter_events_for_user(events=events, user=current_user)

    async def send_daily_alerts(self, organization_id: int) -> int:
        """Sends one consolidated expiring-contract email per subscribed user."""
        events = await self.list_due_events(organization_id=organization_id)
        if not events:
            logger.info("Sin alertas de contratos para org {}. No se envían correos.", organization_id)
            return 0

        recipients = await self._get_notification_recipients(organization_id=organization_id)
        if not recipients:
            logger.info("Sin usuarios suscritos a notificaciones para org {}.", organization_id)
            return 0

        date_str = date.today().strftime("%d/%m/%Y")
        gmail_service = self.gmail_service or GmailService()
        self.gmail_service = gmail_service

        sent = 0
        for recipient in recipients:
            recipient_events = self._filter_events_for_user(events=events, user=recipient)
            if not recipient_events:
                continue

            recipient_events_by_days: dict[int, list[DocumentTable]] = defaultdict(list)
            for event in recipient_events:
                recipient_events_by_days[event.days_remaining].append(event.document)

            total_contracts = len(recipient_events)
            sections_html = self._build_sections(recipient_events_by_days)
            subject = f"ContractAI - {total_contracts} contrato(s) con alertas hoy"
            name = html.escape(recipient.full_name or recipient.email)
            body = self._build_email_html(
                name=name,
                total=total_contracts,
                sections=sections_html,
                date_str=date_str,
            )
            try:
                await gmail_service.send_email(
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
        org_ids = await self._get_active_organization_ids()

        total_sent = 0
        orgs_processed = 0
        orgs_skipped = 0

        for org_id in org_ids:
            already_sent = await self._check_send_log(organization_id=org_id, sent_date=today)
            if already_sent:
                logger.info("Org {} ya recibió correos hoy ({}). Saltando.", org_id, today)
                orgs_skipped += 1
                continue

            sent = await self.send_daily_alerts(organization_id=org_id)
            await self._record_send_log(organization_id=org_id, sent_date=today, emails_sent=sent)
            total_sent += sent
            orgs_processed += 1

        logger.info(
            "Cron finalizado: {} correos enviados, {} orgs procesadas, {} orgs saltadas.",
            total_sent, orgs_processed, orgs_skipped,
        )
        return {"emails_sent": total_sent, "orgs_processed": orgs_processed, "orgs_skipped": orgs_skipped}

    async def _get_active_organization_ids(self) -> list[int]:
        """Returns distinct organization IDs that have at least one active subscribed user."""
        try:
            result = await self.session.exec(
                select(UserTable.organization_id)
                .where(
                    UserTable.is_active.is_(True),
                    UserTable.receives_notifications.is_(True),
                )
                .distinct()
            )
            return list(result.all())
        except OperationalError as e:
            raise ServiceUnavailableError("La base de datos no está disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al consultar organizaciones activas") from e

    async def _check_send_log(self, organization_id: int, sent_date: date) -> bool:
        """Returns True if a send log entry already exists for this org and date."""
        try:
            result = await self.session.exec(
                select(NotificationSendLog).where(
                    NotificationSendLog.organization_id == organization_id,
                    NotificationSendLog.sent_date == sent_date,
                )
            )
            return result.first() is not None
        except SQLAlchemyError as e:
            raise InternalServerError("Error al consultar el log de envíos") from e

    async def _record_send_log(self, organization_id: int, sent_date: date, emails_sent: int) -> None:
        """Records a send log entry. Ignores conflicts (race condition safety)."""
        try:
            log_entry = NotificationSendLog(
                organization_id=organization_id,
                sent_date=sent_date,
                emails_sent=emails_sent,
                created_at=datetime.now(UTC),
            )
            self.session.add(log_entry)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            logger.warning("Send log ya existe para org {} / {}. Ignorando.", organization_id, sent_date)
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise InternalServerError("Error al registrar el log de envío") from e

    async def _get_active_rule_map(self, organization_id: int) -> tuple[dict[int, list[int]], list[int]]:
        try:
            result = await self.session.exec(
                select(NotificationRuleTable)
                .where(
                    NotificationRuleTable.organization_id == organization_id,
                    NotificationRuleTable.is_active.is_(True),
                )
                .order_by(col(NotificationRuleTable.document_id), col(NotificationRuleTable.days_before_due).desc())
            )
            rules = list(result.all())
        except OperationalError as e:
            raise ServiceUnavailableError("La base de datos no está disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al consultar reglas de notificación") from e

        rules_by_document: dict[int, list[int]] = defaultdict(list)
        organization_default_days: list[int] = []

        for rule in rules:
            if rule.document_id is None:
                organization_default_days.append(rule.days_before_due)
                continue
            rules_by_document[rule.document_id].append(rule.days_before_due)

        deduped_rules = {document_id: sorted(set(days), reverse=True) for document_id, days in rules_by_document.items()}
        return deduped_rules, sorted(set(organization_default_days), reverse=True)

    async def _get_documents_for_notification_evaluation(
        self,
        organization_id: int,
        today: date,
    ) -> list[DocumentTable]:
        try:
            result = await self.session.exec(
                select(DocumentTable).where(
                    DocumentTable.organization_id == organization_id,
                    col(DocumentTable.name).is_not(None),
                    col(DocumentTable.client).is_not(None),
                    col(DocumentTable.state).in_([DocumentState.ACTIVE, DocumentState.EXPIRING_SOON]),
                    DocumentTable.end_date >= today,
                )
            )
            return list(result.all())
        except OperationalError as e:
            raise ServiceUnavailableError("La base de datos no está disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al consultar contratos") from e

    async def _get_notification_recipients(self, organization_id: int) -> list[UserTable]:
        try:
            result = await self.session.exec(
                select(UserTable).where(
                    UserTable.organization_id == organization_id,
                    UserTable.is_active.is_(True),
                    UserTable.receives_notifications.is_(True),
                )
            )
            return list(result.all())
        except OperationalError as e:
            raise ServiceUnavailableError("La base de datos no está disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al consultar usuarios") from e

    def _build_sections(self, contracts_by_threshold: dict[int, list[DocumentTable]]) -> str:
        sections = []
        for days in sorted(contracts_by_threshold):
            docs = contracts_by_threshold[days]
            notification_type = self._resolve_notification_type(days_remaining=days)
            badge_color, bg_color, border_color, text_color, subtext_color, label, badge_prefix = self._resolve_threshold_styles(
                notification_type=notification_type
            )

            items_html = ""
            for index, doc in enumerate(docs):
                is_last = index == len(docs) - 1
                border_bottom = "" if is_last else f"border-bottom:1px solid {border_color};"
                items_html += f"""
                <div style=\"padding:14px 18px;background:{bg_color};{border_bottom}\">
                  <p style=\"margin:0 0 3px;color:{text_color};font-size:14px;font-weight:600;\">{html.escape(doc.name)}</p>
                  <p style=\"margin:0;color:{subtext_color};font-size:13px;\">
                    Cliente: {html.escape(doc.client)}&nbsp;&nbsp;·&nbsp;&nbsp;Vence: {doc.end_date.strftime("%d/%m/%Y")}
                  </p>
                </div>"""

            sections.append(
                f"""
            <div style=\"margin-bottom:20px;\">
              <div style=\"margin-bottom:10px;\">
                <span style=\"display:inline-block;background:{badge_color};color:#ffffff;font-size:11px;font-weight:700;
                             letter-spacing:0.4px;padding:4px 14px;border-radius:20px;\">
                  {badge_prefix} VENCE EN {days} DIAS - {label}
                </span>
              </div>
              <div style=\"border-radius:8px;overflow:hidden;border:1px solid {border_color};\">
                {items_html}
              </div>
            </div>"""
            )

        return "\n".join(sections)

    def _build_email_html(self, name: str, total: int, sections: str, date_str: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ContractAI - Alertas de contratos</title>
</head>
<body style="margin:0;padding:0;background-color:#F1F5F9;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background-color:#F1F5F9;padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">

          <tr>
            <td style="background:linear-gradient(135deg,#1E3A8A 0%,#3B82F6 100%);
                       padding:36px 40px;border-radius:12px 12px 0 0;text-align:center;">
              <div style="display:inline-block;background:rgba(255,255,255,0.15);
                          border-radius:8px;padding:8px 24px;margin-bottom:14px;">
                <span style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:1px;">
                  ContractAI
                </span>
              </div>
              <p style="margin:0;color:#BFDBFE;font-size:12px;letter-spacing:0.8px;text-transform:uppercase;">
                Resumen de alertas &nbsp;·&nbsp; {date_str}
              </p>
            </td>
          </tr>

          <tr>
            <td style="background:#ffffff;padding:36px 40px;">

              <p style="margin:0 0 6px;color:#111827;font-size:17px;font-weight:600;">
                Hola, {name}
              </p>
              <p style="margin:0 0 28px;color:#6B7280;font-size:14px;line-height:1.7;">
                Tienes <strong style="color:#1E3A8A;">{total} contrato(s)</strong>
                que requieren tu atención hoy.
              </p>

              {sections}

              <div style="margin-top:24px;padding:16px 20px;background:#F0F9FF;
                          border-radius:8px;border-left:4px solid #3B82F6;">
                <p style="margin:0;color:#1E40AF;font-size:13px;line-height:1.7;">
                  Tip: Accede a ContractAI para revisar los detalles, renovar contratos o gestionar las alertas.
                </p>
              </div>

            </td>
          </tr>

          <tr>
            <td style="background:#F8FAFC;padding:24px 40px;
                       border-radius:0 0 12px 12px;border-top:1px solid #E2E8F0;">
              <p style="margin:0 0 4px;color:#9CA3AF;font-size:12px;text-align:center;">
                Enviado automáticamente por
                <strong style="color:#6B7280;">ContractAI</strong>
              </p>
              <p style="margin:0;color:#B0BAC5;font-size:11px;text-align:center;">
                Por favor no respondas a este mensaje.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
