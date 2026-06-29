"""Contract origin dashboard service mixin."""

from ....documents.domain.value_objs import DocumentType
from ....users.domain.entities import UserTable
from ...domain.access_policy import ensure_dashboard_access
from ..dto import ContractOriginResponse, OriginDistributionPoint
from .helpers import DashboardServiceProtocol


class DashboardOriginServiceMixin:
    """Mixin implementing contract origin dashboard calculations."""

    async def get_labor_origin_dashboard(
        self: DashboardServiceProtocol,
        current_user: UserTable,
    ) -> ContractOriginResponse:
        """Returns the contract origin and creation type dashboard for labor contracts."""
        # Enforce HR / Labor dashboard permissions
        ensure_dashboard_access(current_user=current_user, document_type=DocumentType.LABOR)

        # Retrieve database queries
        distribution_data = await self.repository.get_contract_origin_distribution(organization_id=current_user.organization_id)

        total_contracts = sum(item["count"] for item in distribution_data)

        distribution = [
            OriginDistributionPoint(
                origin_type=item["origin_type"],
                count=item["count"],
                percentage=item["percentage"],
            )
            for item in distribution_data
        ]

        return ContractOriginResponse(
            distribution=distribution,
            total_contracts=total_contracts,
        )
