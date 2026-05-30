"""Rankings queries for dashboard analytics."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import desc, func
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, select

from ....catalog.domain.entities import ServiceTable
from ....documents.domain import CompanyContractServiceTable, CompanyContractTable, DocumentTable
from ....documents.domain.value_objs import CurrencyType
from ...application.repositories import DashboardClientRanking, DashboardServiceRanking
from ...domain.exceptions import DashboardDatabaseError, DashboardDatabaseUnavailableError
from ...domain.value_objs import TopRankingSortBy
from .helpers import DashboardRepositoryProtocol


class DashboardRankingQueriesMixin:
    """Query mixin for retrieving rankings of top companies and top services."""

    async def list_top_companies(
        self: DashboardRepositoryProtocol,
        organization_id: int,
        limit: int,
        currency: CurrencyType | None = None,
        sort_by: TopRankingSortBy = TopRankingSortBy.VOLUME,
    ) -> Sequence[DashboardClientRanking]:
        """Lists company counterparties ranked by contract count and amount."""
        try:
            filters = list(self._base_contract_filters(organization_id=organization_id))
            if currency:
                filters.append(col(CompanyContractServiceTable.currency) == currency)

            statement = (
                select(
                    col(CompanyContractTable.client).label("name"),
                    func.count(func.distinct(col(DocumentTable.id))).label("contracts"),
                    func.coalesce(func.sum(col(CompanyContractServiceTable.value)), 0.0).label("amount"),
                )
                .join(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id))
                .outerjoin(CompanyContractServiceTable, col(CompanyContractServiceTable.company_contract_id) == col(CompanyContractTable.id))
                .where(*filters)
                .group_by(col(CompanyContractTable.client))
            )

            if sort_by == TopRankingSortBy.VALUE:
                statement = statement.order_by(desc("amount"), desc("contracts"), col(CompanyContractTable.client))
            else:
                statement = statement.order_by(desc("contracts"), desc("amount"), col(CompanyContractTable.client))

            statement = statement.limit(limit)

            result = await self.session.exec(statement=statement)
            rankings = []
            for row in result.all():
                mapping = self._extract_mapping(row)
                rankings.append(
                    DashboardClientRanking(
                        name=mapping["name"],
                        contracts=int(mapping["contracts"] or 0),
                        amount=float(mapping["amount"] or 0.0),
                    )
                )
            return rankings
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DashboardDatabaseUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise DashboardDatabaseError("Error al listar empresas principales") from e

    async def list_top_services(
        self: DashboardRepositoryProtocol,
        organization_id: int,
        limit: int,
        currency: CurrencyType | None = None,
        sort_by: TopRankingSortBy = TopRankingSortBy.VOLUME,
    ) -> Sequence[DashboardServiceRanking]:
        """Lists services ranked by associated company contracts and amount."""
        try:
            filters = [
                *self._base_contract_filters(organization_id=organization_id),
                col(ServiceTable.organization_id) == organization_id,
            ]
            if currency:
                filters.append(col(CompanyContractServiceTable.currency) == currency)

            statement = (
                select(
                    col(ServiceTable.name).label("name"),
                    func.count(func.distinct(col(DocumentTable.id))).label("quantity"),
                    func.coalesce(func.sum(col(CompanyContractServiceTable.value)), 0.0).label("amount"),
                )
                .join(CompanyContractServiceTable, col(CompanyContractServiceTable.service_id) == col(ServiceTable.id))
                .join(CompanyContractTable, col(CompanyContractTable.id) == col(CompanyContractServiceTable.company_contract_id))
                .join(DocumentTable, col(DocumentTable.id) == col(CompanyContractTable.document_id))
                .where(*filters)
                .group_by(col(ServiceTable.name))
            )

            if sort_by == TopRankingSortBy.VALUE:
                statement = statement.order_by(desc("amount"), desc("quantity"), col(ServiceTable.name))
            else:
                statement = statement.order_by(desc("quantity"), desc("amount"), col(ServiceTable.name))

            statement = statement.limit(limit)

            result = await self.session.exec(statement=statement)
            rankings = []
            for row in result.all():
                mapping = self._extract_mapping(row)
                rankings.append(
                    DashboardServiceRanking(
                        name=mapping["name"],
                        quantity=int(mapping["quantity"] or 0),
                        amount=float(mapping["amount"] or 0.0),
                    )
                )
            return rankings
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DashboardDatabaseUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise DashboardDatabaseError("Error al listar servicios principales") from e
