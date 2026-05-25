"""Chart metrics queries for dashboard analytics."""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, select

from .....core.exceptions.base import InternalServerError, ServiceUnavailableError
from ....documents.domain import CompanyContractServiceTable, CompanyContractTable, DocumentTable, LaborContractTable
from ....documents.domain.value_objs import CurrencyType, DocumentType
from ...application.repositories import DashboardMonthlyAmount
from .helpers import DashboardRepositoryProtocol


class DashboardChartQueriesMixin:
    """Query mixin for building billing and salary trend charts."""

    async def get_monthly_amounts(
        self: DashboardRepositoryProtocol,
        organization_id: int,
        document_type: DocumentType,
        currency: CurrencyType | None,
        start_month: date,
        months: int,
    ) -> Sequence[DashboardMonthlyAmount]:
        """Returns monthly service amount totals for active contracts."""
        try:
            results: list[DashboardMonthlyAmount] = []
            current_month = start_month
            for _ in range(months):
                next_month = self._month_end(current_month)

                if document_type == DocumentType.COMPANY:
                    filters = [
                        *self._base_contract_filters(organization_id=organization_id),
                        col(CompanyContractServiceTable.value) > 0,
                        col(CompanyContractServiceTable.start_date) < next_month,
                        col(CompanyContractServiceTable.end_date) >= current_month,
                    ]
                    if currency:
                        filters.append(col(CompanyContractServiceTable.currency) == currency)

                    statement = (
                        select(func.coalesce(func.sum(col(CompanyContractServiceTable.value)), 0.0))
                        .select_from(DocumentTable)
                        .join(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id))
                        .join(CompanyContractServiceTable, col(CompanyContractServiceTable.company_contract_id) == col(CompanyContractTable.id))
                        .where(*filters)
                    )
                else:
                    filters = [
                        *self._base_contract_filters(organization_id=organization_id),
                        col(LaborContractTable.salary_value) > 0,
                        col(DocumentTable.start_date) < next_month,
                        col(DocumentTable.end_date) >= current_month,
                    ]
                    if currency:
                        filters.append(col(LaborContractTable.salary_currency) == currency)

                    statement = (
                        select(func.coalesce(func.sum(col(LaborContractTable.salary_value)), 0.0))
                        .select_from(DocumentTable)
                        .join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
                        .where(*filters)
                    )
                result = await self.session.exec(statement=statement)
                results.append(DashboardMonthlyAmount(month=current_month, amount=float(result.one() or 0.0)))
                current_month = next_month
            return results
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al consultar montos mensuales del dashboard") from e
