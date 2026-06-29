"""Email rendering helpers for contract alert notifications."""

import html
from collections import defaultdict
from datetime import date

from .....modules.notifications.application.dto import NotificationDocument, NotificationEvent, NotificationRecipient
from .....modules.notifications.domain import NotificationType

CRITICAL_ALERT_DAYS = 3
WARNING_ALERT_DAYS = 7


class NotificationEmailRenderer:
    """Builds HTML email content for due contract notifications."""

    @staticmethod
    def _resolve_notification_type(days_remaining: int) -> NotificationType:
        if days_remaining <= CRITICAL_ALERT_DAYS:
            return NotificationType.CRITICAL
        if days_remaining <= WARNING_ALERT_DAYS:
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

    def build_email(self, recipient: NotificationRecipient, events: list[NotificationEvent], sent_date: date) -> tuple[str, str]:
        """Returns subject and HTML body for a recipient."""
        events_by_days: dict[int, list[NotificationDocument]] = defaultdict(list)
        for event in events:
            events_by_days[event.days_remaining].append(event.document)

        total_contracts = len(events)
        subject = f"ContractAI - {total_contracts} contrato(s) con alertas hoy"
        body = self._build_email_html(
            name=html.escape(recipient.full_name or recipient.email),
            total=total_contracts,
            sections=self._build_sections(events_by_days),
            date_str=sent_date.strftime("%d/%m/%Y"),
        )
        return subject, body

    def _build_sections(self, contracts_by_threshold: dict[int, list[NotificationDocument]]) -> str:
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
                doc_name = html.escape(doc.file_name or "Contrato sin archivo")
                items_html += f"""
                <div style=\"padding:14px 18px;background:{bg_color};{border_bottom}\">
                  <p style=\"margin:0 0 3px;color:{text_color};font-size:14px;font-weight:600;\">{doc_name}</p>
                  <p style=\"margin:0;color:{subtext_color};font-size:13px;\">
                    Tipo: {html.escape(doc.type or 'sin tipo')}&nbsp;&nbsp;·&nbsp;&nbsp;Vence: {doc.end_date.strftime("%d/%m/%Y")}
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
