"""Contracts cards mixin for dashboard application service."""

from collections.abc import Sequence

from ....documents.domain.value_objs import DocumentType
from ....users.domain.entities import UserTable
from ...domain.access_policy import ensure_dashboard_access
from ..dto import RecentContractResponse
from ..repositories import DashboardContractSummary
from .helpers import RECENT_CONTRACTS_LIMIT, DashboardServiceHelpers, DashboardServiceProtocol


class DashboardContractServiceMixin:
    """Mixin implementing recent contracts query and serialization."""

    @classmethod
    def _serialize_recent_contract(cls, contract: DashboardContractSummary) -> RecentContractResponse:
        return RecentContractResponse(
            id=contract.id,
            title=contract.title,
            services=contract.service_names,
            name=contract.name,
            dates=DashboardServiceHelpers._format_date_range(start_date=contract.start_date, end_date=contract.end_date),
        )

    async def get_recent_contracts(
        self: DashboardServiceProtocol,
        current_user: UserTable,
        document_type: DocumentType,
    ) -> Sequence[RecentContractResponse]:
        """Returns the latest contract cards for one dashboard scope."""
        ensure_dashboard_access(current_user=current_user, document_type=document_type)
        await self.repository.sync_contract_states(organization_id=current_user.organization_id)
        contracts = await self.repository.list_recent_contracts(
            organization_id=current_user.organization_id,
            document_type=document_type,
            limit=RECENT_CONTRACTS_LIMIT,
        )
        return [DashboardContractServiceMixin._serialize_recent_contract(contract) for contract in contracts]
