"""Repository contracts for dashboard analytics."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from ...documents.domain.value_objs import CurrencyType, DocumentState, DocumentType
from ..domain.value_objs import TopRankingSortBy


@dataclass(frozen=True)
class DashboardMonthlyAmount:
    """Monthly aggregated amount for chart series."""

    month: date
    amount: float


@dataclass(frozen=True)
class DashboardContractSummary:
    """Lightweight contract projection for dashboard cards."""

    id: int
    title: str
    name: str
    start_date: date | None
    end_date: date | None
    state: DocumentState | None = None
    detail: str | None = None
    amount: float = 0.0
    service_names: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class DashboardClientRanking:
    """Aggregated ranking row by contract counterparty."""

    name: str
    contracts: int
    amount: float


@dataclass(frozen=True)
class DashboardServiceRanking:
    """Aggregated ranking row by service."""

    name: str
    quantity: int
    amount: float


class DashboardRepository(ABC):
    """Read-only repository contract for dashboard analytics."""

    @abstractmethod
    async def sync_contract_states(self, organization_id: int) -> int:
        """Synchronizes persisted contract states for one organization."""
        pass

    @abstractmethod
    async def get_monthly_amounts(
        self,
        organization_id: int,
        document_type: DocumentType,
        currency: CurrencyType | None,
        start_month: date,
        months: int,
    ) -> Sequence[DashboardMonthlyAmount]:
        """Returns monthly amount aggregates for the requested scope."""
        pass

    @abstractmethod
    async def count_contracts_due_between(
        self,
        organization_id: int,
        document_type: DocumentType,
        start_date: date,
        end_date: date,
    ) -> int:
        """Counts contracts ending inside the provided date range."""
        pass

    @abstractmethod
    async def list_contracts_due_between(
        self,
        organization_id: int,
        document_type: DocumentType,
        start_date: date,
        end_date: date,
        limit: int,
    ) -> Sequence[DashboardContractSummary]:
        """Lists contracts ending inside the provided date range."""
        pass

    @abstractmethod
    async def count_long_term_contracts(
        self,
        organization_id: int,
        document_type: DocumentType,
        after_date: date,
    ) -> int:
        """Counts active contracts whose end date is beyond the alert window."""
        pass

    @abstractmethod
    async def list_long_term_contracts(
        self,
        organization_id: int,
        document_type: DocumentType,
        after_date: date,
        limit: int,
    ) -> Sequence[DashboardContractSummary]:
        """Lists active contracts whose end date is beyond the alert window."""
        pass

    @abstractmethod
    async def list_recent_contracts(
        self,
        organization_id: int,
        document_type: DocumentType,
        limit: int,
    ) -> Sequence[DashboardContractSummary]:
        """Lists recently updated contracts for a document type."""
        pass

    @abstractmethod
    async def list_top_companies(
        self,
        organization_id: int,
        limit: int,
        currency: CurrencyType | None = None,
        sort_by: TopRankingSortBy = TopRankingSortBy.VOLUME,
    ) -> Sequence[DashboardClientRanking]:
        """Lists top company counterparties by contracts and amount."""
        pass

    @abstractmethod
    async def list_top_services(
        self,
        organization_id: int,
        limit: int,
        currency: CurrencyType | None = None,
        sort_by: TopRankingSortBy = TopRankingSortBy.VOLUME,
    ) -> Sequence[DashboardServiceRanking]:
        """Lists top services associated with company contracts."""
        pass
