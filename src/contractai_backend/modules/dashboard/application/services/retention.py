"""Retention dashboard service mixin."""

from ....documents.domain.value_objs import DocumentType
from ....users.domain.entities import UserTable
from ...domain.access_policy import ensure_dashboard_access
from ..dto import (
    MonthlyRenewalPoint,
    RetentionDashboardResponse,
    RetentionKPIs,
    TenureDistributionPoint,
    WorkerRetentionDetail,
)
from .helpers import DashboardServiceProtocol


class DashboardRetentionServiceMixin:
    """Mixin implementing worker retention dashboard calculations."""

    async def get_labor_retention_dashboard(
        self: DashboardServiceProtocol,
        current_user: UserTable,
    ) -> RetentionDashboardResponse:
        """Returns the retention analytics dashboard for labor contracts."""
        # Enforce HR / Labor dashboard permissions
        ensure_dashboard_access(current_user=current_user, document_type=DocumentType.LABOR)

        # Sync states before calculation
        await self.repository.sync_contract_states(organization_id=current_user.organization_id)

        # Retrieve database queries
        kpis_data = await self.repository.get_retention_kpi_data(organization_id=current_user.organization_id)
        distribution_data = await self.repository.get_tenure_distribution(organization_id=current_user.organization_id)
        trend_data = await self.repository.get_monthly_renewal_trend(organization_id=current_user.organization_id)
        details_data = await self.repository.get_worker_retention_details(organization_id=current_user.organization_id)

        # Build response DTOs
        kpis = RetentionKPIs(
            active_retention_rate=kpis_data["active_retention_rate"],
            total_unique_workers=kpis_data["total_unique_workers"],
            avg_contracts_per_worker=kpis_data["avg_contracts_per_worker"],
        )

        tenure_distribution = [
            TenureDistributionPoint(
                contracts_count=item["contracts_count"],
                workers_count=item["workers_count"],
            )
            for item in distribution_data
        ]

        renewal_trend = [
            MonthlyRenewalPoint(
                month=item["month"],
                renewal_rate=item["renewal_rate"],
                total_expired=item["total_expired"],
                total_renewed=item["total_renewed"],
            )
            for item in trend_data
        ]

        details = [
            WorkerRetentionDetail(
                worker_name=item["worker_name"],
                worker_document_number=item["worker_document_number"],
                contracts_count=item["contracts_count"],
                first_contract_start=item["first_contract_start"],
                latest_contract_end=item["latest_contract_end"],
            )
            for item in details_data
        ]

        return RetentionDashboardResponse(
            kpis=kpis,
            tenure_distribution=tenure_distribution,
            renewal_trend=renewal_trend,
            details=details,
        )
