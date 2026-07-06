"""Alert logic mixin for dashboard application service."""

from datetime import date, timedelta

from ....documents.domain.value_objs import DocumentType
from ....users.domain.entities import UserTable
from ...domain.access_policy import ensure_dashboard_access
from ..dto import AlertCategory, AlertColor, AlertItem
from ..repositories import DashboardContractSummary
from .helpers import ALERT_PREVIEW_LIMIT, DashboardServiceProtocol


class DashboardAlertServiceMixin:
    """Mixin implementing alert counting and details mapping for dashboard."""

    @staticmethod
    def _resolve_alert_detail(document_type: DocumentType, contract: DashboardContractSummary) -> str | None:
        if contract.detail:
            return contract.detail
        if document_type == DocumentType.COMPANY:
            return (contract.service_names or [None])[0]
        return None

    @staticmethod
    def _serialize_alert_item(
        document_type: DocumentType,
        contract: DashboardContractSummary,
        today: date,
        *,
        long_term: bool = False,
    ) -> AlertItem:
        days_remaining = (contract.end_date - today).days if contract.end_date else None
        if long_term or days_remaining is None:
            status = "VIGENCIA PROLONGADA"
        elif days_remaining == 1:
            status = "VENCE EN 1 DIA"
        else:
            status = f"VENCE EN {days_remaining} DIAS"

        return AlertItem(
            id=contract.id,
            name=contract.name,
            detail=DashboardAlertServiceMixin._resolve_alert_detail(document_type=document_type, contract=contract),
            status=status,
        )

    async def get_alert_center(
        self: DashboardServiceProtocol,
        current_user: UserTable,
        document_type: DocumentType,
    ) -> list[AlertCategory]:
        """Builds alert buckets for contracts close to renewal plus long-term active contracts."""
        ensure_dashboard_access(current_user=current_user, document_type=document_type)
        await self.repository.sync_contract_states(organization_id=current_user.organization_id)

        today = date.today()
        critical_end = today + timedelta(days=30)
        warning_start = critical_end + timedelta(days=1)
        warning_end = today + timedelta(days=60)

        critical_count = await self.repository.count_contracts_due_between(current_user.organization_id, document_type, today, critical_end)
        warning_count = await self.repository.count_contracts_due_between(current_user.organization_id, document_type, warning_start, warning_end)
        long_term_count = await self.repository.count_long_term_contracts(current_user.organization_id, document_type, warning_end)

        critical_items = await self.repository.list_contracts_due_between(
            current_user.organization_id,
            document_type,
            today,
            critical_end,
            ALERT_PREVIEW_LIMIT,
        )
        warning_items = await self.repository.list_contracts_due_between(
            current_user.organization_id,
            document_type,
            warning_start,
            warning_end,
            ALERT_PREVIEW_LIMIT,
        )
        long_term_items = await self.repository.list_long_term_contracts(
            current_user.organization_id,
            document_type,
            warning_end,
            ALERT_PREVIEW_LIMIT,
        )

        return [
            AlertCategory(
                label="VENCEN PROXIMOS",
                color=AlertColor(accent="#EF4444", bg="#FEE2E2"),
                due_to=30,
                count=critical_count,
                items=[DashboardAlertServiceMixin._serialize_alert_item(document_type, item, today) for item in critical_items],
            ),
            AlertCategory(
                label="VENCEN PROXIMOS",
                color=AlertColor(accent="#F59E0B", bg="#FEF3C7"),
                due_to=60,
                count=warning_count,
                items=[DashboardAlertServiceMixin._serialize_alert_item(document_type, item, today) for item in warning_items],
            ),
            AlertCategory(
                label="VIGENCIA PROLONGADA",
                color=AlertColor(accent="#059669", bg="#D1FAE5"),
                due_to=None,
                count=long_term_count,
                items=[DashboardAlertServiceMixin._serialize_alert_item(document_type, item, today, long_term=True) for item in long_term_items],
            ),
        ]
