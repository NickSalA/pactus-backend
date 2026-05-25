"""Chart logic mixin for dashboard application service."""

from datetime import UTC, date, datetime, time

from ....documents.domain.value_objs import CurrencyType, DocumentType
from ....users.domain.entities import UserTable
from ...domain.access_policy import ensure_dashboard_access
from ..dto import AreaChartPoint, AreaChartProps, AreaChartResponse, AreaChartSeries, AreaChartYAxis
from .helpers import (
    AREA_CHART_FORECAST_MONTHS,
    AREA_CHART_HISTORY_MONTHS,
    MONTH_LABELS,
    DashboardServiceProtocol,
)


class DashboardChartServiceMixin:
    """Mixin implementing area chart billing and salary projection logic."""

    @staticmethod
    def _resolve_chart_copy(document_type: DocumentType) -> tuple[str, str, str]:
        if document_type == DocumentType.COMPANY:
            return "Ingresos Proyectados", "Historico vs. contratos asegurados a futuro", "Ingresos"
        return "Gasto de Planilla", "Costo historico y reduccion por fin de contratos", "Gasto"

    async def get_area_chart(
        self: DashboardServiceProtocol,
        current_user: UserTable,
        document_type: DocumentType,
        currency: CurrencyType | None = None,
    ) -> AreaChartResponse:
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
            currency=currency,
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

        title, subtitle, series_name = DashboardChartServiceMixin._resolve_chart_copy(document_type=document_type)
        max_value = max((point.y for point in points), default=0.0)

        series = [AreaChartSeries(currency=currency or "ALL", name=series_name, data=points)]

        return AreaChartResponse(
            props=AreaChartProps(
                title=title,
                subtitle=subtitle,
                y_axis=AreaChartYAxis(labels=self._build_y_axis_labels(max_value=max_value)),
                threshold_date=datetime.combine(current_month, time.min, tzinfo=UTC),
                series=series,
            )
        )
