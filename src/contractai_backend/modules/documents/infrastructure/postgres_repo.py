"""Repositorio de Documentos utilizando SQLModel y AsyncSession para Supabase."""

from collections import defaultdict
from collections.abc import Sequence

from loguru import logger
from sqlalchemy import Float, cast, func
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....core.infrastructure.base import PostgresBaseRepository
from ..application.dto import ContractQueryDTO
from ..application.repositories import DocumentCommandRepository, DocumentQueryRepository, ServiceCatalogRepository
from ..domain import DocumentServiceTable, DocumentTable, ServiceTable
from ..domain.exceptions import DocumentDatabaseError, DocumentDatabaseUnavailableError


class SQLModelDocumentRepository(
    PostgresBaseRepository[DocumentTable],
    DocumentQueryRepository,
    DocumentCommandRepository,
    ServiceCatalogRepository,
):
    """Repositorio de Documentos utilizando SQLModel y AsyncSession para Supabase."""

    def __init__(self, session: AsyncSession):
        super().__init__(model=DocumentTable, session=session)

    @staticmethod
    def _normalize_text_filter(value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = value.strip().lower()
        return cleaned or None

    @staticmethod
    def _build_contract_value_expression():
        return cast(DocumentTable.form_data["value"].astext, Float)

    def _apply_period_filters(self, statement, filters: ContractQueryDTO):
        if not (filters.period_start or filters.period_end):
            return statement

        default_columns = (col(DocumentTable.end_date), col(DocumentTable.start_date))

        mode_columns = {
            "start_date": (col(DocumentTable.start_date), col(DocumentTable.start_date)),
            "end_date": (col(DocumentTable.end_date), col(DocumentTable.end_date)),
            "overlap": default_columns,
        }

        period_start_column, period_end_column = mode_columns.get(filters.date_mode, default_columns)

        if filters.period_start is not None:
            statement = statement.where(period_start_column >= filters.period_start)
        if filters.period_end is not None:
            statement = statement.where(period_end_column <= filters.period_end)
        return statement

    def _apply_contract_filters(
        self,
        statement,
        organization_id: int,
        filters: ContractQueryDTO,
    ):
        """Aplica los filtros de búsqueda de contratos a la consulta base."""
        statement = statement.where(DocumentTable.organization_id == organization_id)

        text_filters = (
            (filters.client, DocumentTable.client),
            (filters.contract_name, DocumentTable.name),
        )
        for raw_value, field in text_filters:
            normalized_value = self._normalize_text_filter(raw_value)
            if normalized_value:
                statement = statement.where(col(field).ilike(f"%{normalized_value}%"))

        contract_value = self._build_contract_value_expression()
        if filters.min_value is not None:
            statement = statement.where(contract_value >= filters.min_value)
        if filters.max_value is not None:
            statement = statement.where(contract_value <= filters.max_value)

        if filters.currency:
            statement = statement.where(func.upper(DocumentTable.form_data["currency"].astext) == filters.currency)

        exact_filters = (
            (filters.state, col(DocumentTable.state)),
            (filters.document_type, col(DocumentTable.type)),
        )
        for value, field in exact_filters:
            if value is not None:
                statement = statement.where(field == value)

        return self._apply_period_filters(statement=statement, filters=filters)

    async def get_document_services(self, doc_id: int) -> Sequence[DocumentServiceTable]:
        """Obtiene los servicios asociados a un documento."""
        try:
            query = select(DocumentServiceTable).where(col(DocumentServiceTable.document_id) == doc_id).order_by(col(DocumentServiceTable.id))
            result = await self.session.exec(statement=query)
            return result.all()
        except OperationalError as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_document_services_by_document_ids(self, document_ids: Sequence[int]) -> dict[int, Sequence[DocumentServiceTable]]:
        """Obtiene los servicios asociados a múltiples documentos en una sola consulta."""
        if not document_ids:
            return {}

        try:
            query = (
                select(DocumentServiceTable)
                .where(col(DocumentServiceTable.document_id).in_(document_ids))
                .order_by(col(DocumentServiceTable.document_id), col(DocumentServiceTable.id))
            )
            result = await self.session.exec(statement=query)
            grouped_services: defaultdict[int, list[DocumentServiceTable]] = defaultdict(list)
            for service_item in result.all():
                grouped_services[service_item.document_id].append(service_item)
            return dict(grouped_services)
        except OperationalError as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def search_contracts(self, organization_id: int, query: ContractQueryDTO, limit: int | None = None) -> Sequence[DocumentTable]:
        """Obtiene contratos aplicando filtros estructurados."""
        try:
            statement = select(DocumentTable).order_by(
                col(DocumentTable.start_date),
                col(DocumentTable.end_date),
                col(DocumentTable.id),
            )
            statement = self._apply_contract_filters(
                statement=statement,
                organization_id=organization_id,
                filters=query,
            )

            if limit is not None:
                statement = statement.limit(limit)

            result = await self.session.exec(statement=statement)
            return result.all()
        except OperationalError as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def count_contracts(self, organization_id: int, query: ContractQueryDTO) -> int:
        """Cuenta contratos aplicando filtros estructurados."""
        try:
            statement = select(func.count()).select_from(DocumentTable)
            statement = self._apply_contract_filters(
                statement=statement,
                organization_id=organization_id,
                filters=query,
            )
            result = await self.session.exec(statement=statement)
            count = result.one()
            return int(count or 0)
        except OperationalError as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def replace_document_services(self, doc_id: int, service_items: Sequence[DocumentServiceTable]) -> Sequence[DocumentServiceTable]:
        """Reemplaza el conjunto de servicios asociados a un documento."""
        try:
            await self.session.exec(delete(DocumentServiceTable).where(col(DocumentServiceTable.document_id) == doc_id))

            if service_items:
                self.session.add_all(service_items)

            await self.session.commit()

            return service_items

        except OperationalError as e:
            await self.session.rollback()
            logger.debug(f"OperationalError replacing services for document {doc_id}: {e}")
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.debug(f"SQLAlchemyError replacing services for document {doc_id}: {e}")
            raise DocumentDatabaseError() from e

    async def get_services_by_ids(self, organization_id: int, service_ids: Sequence[int]) -> Sequence[ServiceTable]:
        """Obtiene los servicios existentes por sus IDs dentro de una organización."""
        if not service_ids:
            return []

        try:
            query = select(ServiceTable).where(
                col(ServiceTable.organization_id) == organization_id,
                col(ServiceTable.id).in_(service_ids),
            )
            result = await self.session.exec(statement=query)
            return result.all()
        except OperationalError as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_services(self, organization_id: int) -> Sequence[ServiceTable]:
        """Obtiene el catálogo de servicios de una organización."""
        try:
            query = (
                select(ServiceTable)
                .where(col(ServiceTable.organization_id) == organization_id)
                .order_by(col(ServiceTable.name), col(ServiceTable.id))
            )
            result = await self.session.exec(statement=query)
            return result.all()
        except OperationalError as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e
