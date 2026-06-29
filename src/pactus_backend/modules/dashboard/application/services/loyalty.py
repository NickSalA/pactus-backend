"""Company client loyalty dashboard service mixin."""

from ....documents.domain.value_objs import DocumentType
from ....users.domain.entities import UserTable
from ...domain.access_policy import ensure_dashboard_access
from ..dto import (
    ClientLoyaltyDetail,
    ClientLoyaltyKPIs,
    ClientMonthlyRenewalPoint,
    ClientTenureDistributionPoint,
    CompanyLoyaltyDashboardResponse,
)
from .helpers import DashboardServiceProtocol


class DashboardCompanyLoyaltyServiceMixin:
    """Mixin implementing B2B client loyalty dashboard calculations."""

    async def get_company_loyalty_dashboard(
        self: DashboardServiceProtocol,
        current_user: UserTable,
    ) -> CompanyLoyaltyDashboardResponse:
        """Returns the loyalty and recurrence analytics dashboard for B2B client contracts."""
        ensure_dashboard_access(current_user=current_user, document_type=DocumentType.COMPANY)

        await self.repository.sync_contract_states(organization_id=current_user.organization_id)

        kpis_data = await self.repository.get_company_loyalty_kpi_data(organization_id=current_user.organization_id)
        distribution_data = await self.repository.get_company_tenure_distribution(organization_id=current_user.organization_id)
        trend_data = await self.repository.get_company_monthly_renewal_trend(organization_id=current_user.organization_id)
        details_data = await self.repository.get_company_loyalty_details(organization_id=current_user.organization_id)

        kpis = ClientLoyaltyKPIs(
            active_retention_rate=kpis_data["active_retention_rate"],
            total_unique_clients=kpis_data["total_unique_clients"],
            avg_contracts_per_client=kpis_data["avg_contracts_per_client"],
        )

        tenure_distribution = [
            ClientTenureDistributionPoint(
                contracts_count=item["contracts_count"],
                clients_count=item["clients_count"],
            )
            for item in distribution_data
        ]

        renewal_trend = [
            ClientMonthlyRenewalPoint(
                month=item["month"],
                renewal_rate=item["renewal_rate"],
                total_expired=item["total_expired"],
                total_renewed=item["total_renewed"],
            )
            for item in trend_data
        ]

        details = [
            ClientLoyaltyDetail(
                client_name=item["client_name"],
                ruc=item["ruc"],
                contracts_count=item["contracts_count"],
                first_contract_start=item["first_contract_start"],
                latest_contract_end=item["latest_contract_end"],
            )
            for item in details_data
        ]

        return CompanyLoyaltyDashboardResponse(
            kpis=kpis,
            tenure_distribution=tenure_distribution,
            renewal_trend=renewal_trend,
            details=details,
        )
