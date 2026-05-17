"""PostgreSQL implementation for dashboard analytics."""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import desc, func, literal, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....core.exceptions.base import InternalServerError, ServiceUnavailableError
from ....shared.infrastructure.sqlmodel_utils import RelationalHelpersMixin
from ...documents.domain import CompanyContractServiceTable, CompanyContractTable, DocumentTable, LaborContractTable, ServiceTable
from ...documents.domain.value_objs import DocumentState, DocumentType, CurrencyType
from ..domain.value_objs import TopRankingSortBy
from ..application.repositories import (
    DashboardClientRanking,
    DashboardContractSummary,
    DashboardMonthlyAmount,
    DashboardRepository,
    DashboardServiceRanking,
)

ACTIVE_DASHBOARD_STATES = (DocumentState.ACTIVE, DocumentState.EXPIRING_SOON)
DECEMBER = 12


class SQLModelDashboardRepository(RelationalHelpersMixin, DashboardRepository):
    """Dashboard repository backed by PostgreSQL via SQLModel."""

    def __init__(self, session: AsyncSession):
        self.session = session

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
                select(
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

        return (
            select(
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
            )
            .join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
        )

    async def sync_contract_states(self, organization_id: int) -> int:
        """Synchronizes document states before dashboard reads."""
        try:
            result = await self.session.exec(
                text("select public.sync_document_states(:organization_id)"),
                params={"organization_id": organization_id},
            )
            return self._read_scalar_result(result.one())
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al sincronizar estados de contratos") from e

    async def get_monthly_amounts(
        self,
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

    async def count_contracts_due_between(
        self,
        organization_id: int,
        document_type: DocumentType,
        start_date: date,
        end_date: date,
    ) -> int:
        """Counts contracts due in a date range."""
        try:
            statement = select(func.count(col(DocumentTable.id)))
            if document_type == DocumentType.COMPANY:
                statement = statement.join(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id))
            else:
                statement = statement.join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
            statement = statement.where(
                *self._base_contract_filters(organization_id=organization_id),
                col(DocumentTable.end_date) >= start_date,
                col(DocumentTable.end_date) <= end_date,
            )
            result = await self.session.exec(statement=statement)
            return int(result.one() or 0)
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al contar contratos en alerta") from e

    async def list_contracts_due_between(
        self,
        organization_id: int,
        document_type: DocumentType,
        start_date: date,
        end_date: date,
        limit: int,
    ) -> Sequence[DashboardContractSummary]:
        """Lists contracts due in a date range."""
        try:
            statement = (
                self._contract_summary_select(document_type=document_type)
                .where(
                    *self._base_contract_filters(organization_id=organization_id),
                    col(DocumentTable.end_date) >= start_date,
                    col(DocumentTable.end_date) <= end_date,
                )
                .order_by(col(DocumentTable.end_date), col(DocumentTable.id))
                .limit(limit)
            )
            result = await self.session.exec(statement=statement)
            return [self._serialize_contract_row(row) for row in result.all()]
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar contratos en alerta") from e

    async def count_long_term_contracts(self, organization_id: int, document_type: DocumentType, after_date: date) -> int:
        """Counts active contracts outside the alert window."""
        try:
            statement = select(func.count(col(DocumentTable.id)))
            if document_type == DocumentType.COMPANY:
                statement = statement.join(CompanyContractTable, col(CompanyContractTable.document_id) == col(DocumentTable.id))
            else:
                statement = statement.join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
            statement = statement.where(
                *self._base_contract_filters(organization_id=organization_id),
                col(DocumentTable.end_date) > after_date,
            )
            result = await self.session.exec(statement=statement)
            return int(result.one() or 0)
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al contar contratos de vigencia prolongada") from e

    async def list_long_term_contracts(
        self,
        organization_id: int,
        document_type: DocumentType,
        after_date: date,
        limit: int,
    ) -> Sequence[DashboardContractSummary]:
        """Lists active contracts outside the alert window."""
        try:
            statement = (
                self._contract_summary_select(document_type=document_type)
                .where(
                    *self._base_contract_filters(organization_id=organization_id),
                    col(DocumentTable.end_date) > after_date,
                )
                .order_by(desc(col(DocumentTable.end_date)), col(DocumentTable.id))
                .limit(limit)
            )
            result = await self.session.exec(statement=statement)
            return [self._serialize_contract_row(row) for row in result.all()]
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar contratos de vigencia prolongada") from e

    async def list_recent_contracts(
        self,
        organization_id: int,
        document_type: DocumentType,
        limit: int,
    ) -> Sequence[DashboardContractSummary]:
        """Lists recently updated contracts."""
        try:
            statement = (
                self._contract_summary_select(document_type=document_type)
                .where(*self._base_contract_filters(organization_id=organization_id))
                .order_by(desc(col(DocumentTable.updated_at)), desc(col(DocumentTable.created_at)), col(DocumentTable.id))
                .limit(limit)
            )
            result = await self.session.exec(statement=statement)
            return [self._serialize_contract_row(row) for row in result.all()]
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar contratos recientes") from e

    async def list_top_companies(
        self,
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
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar empresas principales") from e

    async def list_top_services(
        self,
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
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar servicios principales") from e
