"""Application service for dashboard analytics."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from math import ceil

from ...documents.domain.value_objs import DocumentType
from ...users.domain.entities import UserTable
from ..api.schemas import (
    AlertCategory,
    AlertColor,
    AlertItem,
    AreaChartPoint,
    AreaChartProps,
    AreaChartResponse,
    AreaChartSeries,
    AreaChartYAxis,
    RecentContractResponse,
    TopCompanyResponse,
    TopServiceResponse,
)
from ..domain.access_policy import ensure_dashboard_access
from .repositories import DashboardContractSummary, DashboardRepository

AREA_CHART_HISTORY_MONTHS = 4
AREA_CHART_FORECAST_MONTHS = 2
ALERT_PREVIEW_LIMIT = 3
RECENT_CONTRACTS_LIMIT = 4
TOP_RANKING_LIMIT = 5
MONTH_LABELS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


class DashboardService:
    """Coordinates dashboard read models and access rules."""

    def __init__(self, repository: DashboardRepository):
        self.repository = repository

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        return date(year, month, 1)

    @staticmethod
    def _month_start(value: date) -> date:
        return date(value.year, value.month, 1)

    @staticmethod
    def _format_date_range(start_date: date | None, end_date: date | None) -> str:
        if start_date is None or end_date is None:
            return "Sin fechas"
        return f"{start_date.strftime('%m/%d/%y')} - {end_date.strftime('%m/%d/%y')}"

    @staticmethod
    def _build_y_axis_labels(max_value: float) -> list[float]:
        if max_value <= 0:
            return [0, 20, 40, 60, 80]

        step = max(1, ceil(max_value / 4 / 1000) * 1000)
        return [float(step * index) for index in range(5)]

    @staticmethod
    def _resolve_chart_copy(document_type: DocumentType) -> tuple[str, str, str]:
        if document_type == DocumentType.COMPANY:
            return "Ingresos Proyectados", "Historico vs. contratos asegurados a futuro", "Ingresos"
        return "Gasto de Planilla", "Costo historico y reduccion por fin de contratos", "Gasto"

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
            detail=DashboardService._resolve_alert_detail(document_type=document_type, contract=contract),
            status=status,
        )

    @classmethod
    def _serialize_recent_contract(cls, contract: DashboardContractSummary) -> RecentContractResponse:
        return RecentContractResponse(
            id=contract.id,
            title=contract.title,
            services=contract.service_names,
            name=contract.name,
            dates=cls._format_date_range(start_date=contract.start_date, end_date=contract.end_date),
        )

    async def get_area_chart(self, current_user: UserTable, document_type: DocumentType) -> AreaChartResponse:
        """Builds historical and future secured-contract amounts for one dashboard scope."""
        ensure_dashboard_access(current_user=current_user, document_type=document_type)
        await self.repository.sync_contract_states(organization_id=current_user.organization_id)

        today = date.today()
        current_month = self._month_start(today)
        start_month = self._add_months(current_month, -AREA_CHART_HISTORY_MONTHS)
        total_months = AREA_CHART_HISTORY_MONTHS + 1 + AREA_CHART_FORECAST_MONTHS
        monthly_amounts = await self.repository.get_monthly_amounts(
            organization_id=current_user.organization_id,
            document_type=document_type,
            start_month=start_month,
            months=total_months,
        )

        points = [
            AreaChartPoint(
                x=MONTH_LABELS[item.month.month - 1],
                y=round(item.amount, 2),
                is_forecast=item.month > current_month,
            )
            for item in monthly_amounts
        ]
        title, subtitle, series_name = self._resolve_chart_copy(document_type=document_type)
        max_value = max((point.y for point in points), default=0)
        return AreaChartResponse(
            props=AreaChartProps(
                title=title,
                subtitle=subtitle,
                y_axis=AreaChartYAxis(labels=self._build_y_axis_labels(max_value=max_value)),
                threshold_date=datetime.combine(current_month, time.min, tzinfo=UTC),
                series=[AreaChartSeries(name=series_name, data=points)],
            )
        )

    async def get_alert_center(self, current_user: UserTable, document_type: DocumentType) -> list[AlertCategory]:
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
                color=AlertColor(accent="#232232", bg="#123421"),
                due_to=30,
                count=critical_count,
                items=[self._serialize_alert_item(document_type, item, today) for item in critical_items],
            ),
            AlertCategory(
                label="VENCEN PROXIMOS",
                color=AlertColor(accent="#F59E0B", bg="#FEF3C7"),
                due_to=60,
                count=warning_count,
                items=[self._serialize_alert_item(document_type, item, today) for item in warning_items],
            ),
            AlertCategory(
                label="VIGENCIA PROLONGADA",
                color=AlertColor(accent="#059669", bg="#D1FAE5"),
                due_to=None,
                count=long_term_count,
                items=[self._serialize_alert_item(document_type, item, today, long_term=True) for item in long_term_items],
            ),
        ]

    async def get_recent_contracts(self, current_user: UserTable, document_type: DocumentType) -> Sequence[RecentContractResponse]:
        """Returns the latest contract cards for one dashboard scope."""
        ensure_dashboard_access(current_user=current_user, document_type=document_type)
        await self.repository.sync_contract_states(organization_id=current_user.organization_id)
        contracts = await self.repository.list_recent_contracts(
            organization_id=current_user.organization_id,
            document_type=document_type,
            limit=RECENT_CONTRACTS_LIMIT,
        )
        return [self._serialize_recent_contract(contract) for contract in contracts]

    async def get_top_companies(self, current_user: UserTable) -> Sequence[TopCompanyResponse]:
        """Returns the top company counterparties for managers."""
        ensure_dashboard_access(current_user=current_user, document_type=DocumentType.COMPANY)
        await self.repository.sync_contract_states(organization_id=current_user.organization_id)
        rows = await self.repository.list_top_companies(organization_id=current_user.organization_id, limit=TOP_RANKING_LIMIT)
        return [TopCompanyResponse(name=row.name, contracts=row.contracts, amount=round(row.amount, 2)) for row in rows]

    async def get_top_services(self, current_user: UserTable) -> Sequence[TopServiceResponse]:
        """Returns the top services for company contracts and managers."""
        ensure_dashboard_access(current_user=current_user, document_type=DocumentType.COMPANY)
        await self.repository.sync_contract_states(organization_id=current_user.organization_id)
        rows = await self.repository.list_top_services(organization_id=current_user.organization_id, limit=TOP_RANKING_LIMIT)
        return [TopServiceResponse(name=row.name, quantity=row.quantity, amount=round(row.amount, 2)) for row in rows]
