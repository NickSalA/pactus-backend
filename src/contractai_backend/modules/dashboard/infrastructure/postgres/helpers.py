"""Shared helpers and serialization for dashboard SQLModel queries."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import func, literal
from sqlalchemy import select as sa_select
from sqlmodel import col

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

from .....core.infrastructure.sqlmodel_utils import RelationalHelpersMixin
from ....catalog.domain.entities import ServiceTable
from ....documents.domain import CompanyContractServiceTable, CompanyContractTable, DocumentTable, LaborContractTable
from ....documents.domain.value_objs import DocumentState, DocumentType
from ...application.repositories import DashboardContractSummary

ACTIVE_DASHBOARD_STATES = (DocumentState.ACTIVE, DocumentState.EXPIRING_SOON)
DECEMBER = 12


class DashboardRepositoryProtocol(Protocol):
    """Protocol defining the interface required by dashboard postgres query mixins."""

    session: AsyncSession

    @staticmethod
    def _month_end(month: date) -> date: ...

    @staticmethod
    def _extract_mapping(row: Any) -> Any: ...

    @classmethod
    def _serialize_contract_row(cls, row: Any) -> DashboardContractSummary: ...

    @staticmethod
    def _base_contract_filters(organization_id: int) -> tuple[Any, ...]: ...

    def _contract_summary_select(self, document_type: DocumentType) -> Any: ...

    def _read_scalar_result(self, value: Any) -> Any: ...


class DashboardRepositoryHelpers(RelationalHelpersMixin):
    """Shared query helpers and serialization for dashboard SQLModel queries."""

    @staticmethod
    def _month_end(month: date) -> date:
        if month.month == DECEMBER:
            return date(month.year + 1, 1, 1)
        return date(month.year, month.month + 1, 1)

    @staticmethod
    def _extract_mapping(row):
        return row._mapping if hasattr(row, "_mapping") else row

    @staticmethod
    def _normalize_service_names(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if not isinstance(value, Sequence):
            return []
        return [str(item) for item in value if item]

    @classmethod
    def _serialize_contract_row(cls, row) -> DashboardContractSummary:
        mapping = cls._extract_mapping(row)
        return DashboardContractSummary(
            id=int(mapping["id"]),
            title=mapping["title"] or "Contrato sin titulo",
            name=mapping["name"] or "Sin contraparte",
            start_date=mapping["start_date"],
            end_date=mapping["end_date"],
            state=mapping["state"],
            detail=mapping["detail"],
            amount=float(mapping["amount"] or 0.0),
            service_names=cls._normalize_service_names(mapping["service_names"]),
            created_at=mapping["created_at"],
            updated_at=mapping["updated_at"],
        )

    @staticmethod
    def _base_contract_filters(organization_id: int):
        return (
            col(DocumentTable.organization_id) == organization_id,
            col(DocumentTable.state).in_(ACTIVE_DASHBOARD_STATES),
        )

    def _contract_summary_select(self, document_type: DocumentType):
        if document_type == DocumentType.COMPANY:
            return (
                sa_select(
                    col(DocumentTable.id).label("id"),
                    col(CompanyContractTable.client).label("title"),
                    col(CompanyContractTable.client).label("name"),
                    col(DocumentTable.start_date).label("start_date"),
                    col(DocumentTable.end_date).label("end_date"),
                    col(DocumentTable.state).label("state"),
                    func.min(col(CompanyContractServiceTable.description)).label("detail"),
                    col(DocumentTable.created_at).label("created_at"),
                    col(DocumentTable.updated_at).label("updated_at"),
                    func.coalesce(func.sum(col(CompanyContractServiceTable.value)), 0.0).label("amount"),
                    func.array_remove(func.array_agg(func.distinct(col(ServiceTable.name))), None).label("service_names"),
                )
                .join(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id))
                .outerjoin(CompanyContractServiceTable, col(CompanyContractServiceTable.company_contract_id) == col(CompanyContractTable.id))
                .outerjoin(ServiceTable, col(ServiceTable.id) == col(CompanyContractServiceTable.service_id))
                .group_by(
                    col(DocumentTable.id),
                    col(CompanyContractTable.client),
                    col(DocumentTable.start_date),
                    col(DocumentTable.end_date),
                    col(DocumentTable.state),
                    col(DocumentTable.created_at),
                    col(DocumentTable.updated_at),
                )
            )

        return sa_select(
            col(DocumentTable.id).label("id"),
            col(LaborContractTable.worker_name).label("title"),
            col(LaborContractTable.worker_name).label("name"),
            col(DocumentTable.start_date).label("start_date"),
            col(DocumentTable.end_date).label("end_date"),
            col(DocumentTable.state).label("state"),
            col(LaborContractTable.position).label("detail"),
            col(DocumentTable.created_at).label("created_at"),
            col(DocumentTable.updated_at).label("updated_at"),
            func.coalesce(col(LaborContractTable.salary_value), 0.0).label("amount"),
            literal(None).label("service_names"),
        ).join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
