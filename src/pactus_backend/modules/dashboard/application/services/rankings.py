"""Rankings logic mixin for dashboard application service."""

from collections.abc import Sequence

from ....documents.domain.value_objs import CurrencyType, DocumentType
from ....users.domain.entities import UserTable
from ...domain.access_policy import ensure_dashboard_access
from ...domain.value_objs import TopRankingSortBy
from ..dto import TopCompanyResponse, TopServiceResponse
from .helpers import TOP_RANKING_LIMIT, DashboardServiceProtocol


class DashboardRankingServiceMixin:
    """Mixin implementing company counterparties and service ranking logic."""

    async def get_top_companies(
        self: DashboardServiceProtocol,
        current_user: UserTable,
        currency: CurrencyType | None = None,
        sort_by: TopRankingSortBy = TopRankingSortBy.VOLUME,
        limit: int | None = None,
    ) -> Sequence[TopCompanyResponse]:
        """Returns the top company counterparties for managers."""
        ensure_dashboard_access(current_user=current_user, document_type=DocumentType.COMPANY)
        await self.repository.sync_contract_states(organization_id=current_user.organization_id)
        rows = await self.repository.list_top_companies(
            organization_id=current_user.organization_id,
            limit=limit or TOP_RANKING_LIMIT,
            currency=currency,
            sort_by=sort_by,
        )
        return [
            TopCompanyResponse(
                name=row.name,
                contracts=row.contracts,
                amount=round(row.amount, 2),
            )
            for row in rows
        ]

    async def get_top_services(
        self: DashboardServiceProtocol,
        current_user: UserTable,
        currency: CurrencyType | None = None,
        sort_by: TopRankingSortBy = TopRankingSortBy.VOLUME,
        limit: int | None = None,
    ) -> Sequence[TopServiceResponse]:
        """Returns the top services for company contracts and managers."""
        ensure_dashboard_access(current_user=current_user, document_type=DocumentType.COMPANY)
        await self.repository.sync_contract_states(organization_id=current_user.organization_id)
        rows = await self.repository.list_top_services(
            organization_id=current_user.organization_id,
            limit=limit or TOP_RANKING_LIMIT,
            currency=currency,
            sort_by=sort_by,
        )
        return [
            TopServiceResponse(
                name=row.name,
                quantity=row.quantity,
                amount=round(row.amount, 2),
            )
            for row in rows
        ]
