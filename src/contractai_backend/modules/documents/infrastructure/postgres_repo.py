"""Repositorio de Documentos utilizando SQLModel y AsyncSession para Supabase."""

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from loguru import logger
from sqlalchemy import Float, cast, func
from sqlalchemy.exc import OperationalError, SQLAlchemyError, TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....core.infrastructure.base import PostgresBaseRepository
from ..application.repositories import DocumentCommandRepository, DocumentQueryRepository, ServiceCatalogRepository
from ..domain import DocumentServiceTable, DocumentTable, ServiceTable
from ..domain.exceptions import DocumentDatabaseError, DocumentDatabaseUnavailableError
from ..domain.value_objs import DocumentState


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

    def _apply_contract_filters(  # noqa: PLR0913
        self,
        query,
        organization_id: int,
        client: str | None = None,
        contract_name: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        currency: str | None = None,
        state: str | None = None,
        document_type: str | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
        date_mode: str = "overlap",
    ):
        query = query.where(DocumentTable.organization_id == organization_id)

        normalized_client = self._normalize_text_filter(client)
        if normalized_client:
            query = query.where(func.lower(DocumentTable.client).like(f"%{normalized_client}%"))

        normalized_contract_name = self._normalize_text_filter(contract_name)
        if normalized_contract_name:
            query = query.where(func.lower(DocumentTable.name).like(f"%{normalized_contract_name}%"))

        contract_value = self._build_contract_value_expression()
        if min_value is not None:
            query = query.where(contract_value >= min_value)
        if max_value is not None:
            query = query.where(contract_value <= max_value)

        if currency:
            query = query.where(func.upper(DocumentTable.form_data["currency"].astext) == currency)

        if state:
            query = query.where(DocumentTable.state == state)

        if document_type:
            query = query.where(DocumentTable.type == document_type)

        if period_start or period_end:
            if date_mode == "start_date":
                if period_start is not None:
                    query = query.where(DocumentTable.start_date >= period_start)
                if period_end is not None:
                    query = query.where(DocumentTable.start_date <= period_end)
            elif date_mode == "end_date":
                if period_start is not None:
                    query = query.where(DocumentTable.end_date >= period_start)
                if period_end is not None:
                    query = query.where(DocumentTable.end_date <= period_end)
            else:
                if period_start is not None:
                    query = query.where(DocumentTable.end_date >= period_start)
                if period_end is not None:
                    query = query.where(DocumentTable.start_date <= period_end)

        return query

    async def get_by_client_name(self, client_name: str) -> Sequence[DocumentTable]:
        """Obtiene los documentos asociados a un cliente."""
        try:
            client_column = DocumentTable.__table__.c.client
            id_column = DocumentTable.__table__.c.id
            query = select(DocumentTable).where(client_column == client_name).order_by(id_column)
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_active_documents(self) -> Sequence[DocumentTable]:
        """Obtiene todos los documentos activos."""
        try:
            state_column = DocumentTable.__table__.c.state
            id_column = DocumentTable.__table__.c.id
            query = select(DocumentTable).where(state_column == DocumentState.ACTIVE).order_by(id_column)
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_document_services(self, document_id: int) -> Sequence[DocumentServiceTable]:
        """Obtiene los servicios asociados a un documento."""
        try:
            document_id_column = DocumentServiceTable.__table__.c.document_id
            id_column = DocumentServiceTable.__table__.c.id
            query = select(DocumentServiceTable).where(document_id_column == document_id).order_by(id_column)
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_document_services_by_document_ids(self, document_ids: Sequence[int]) -> dict[int, Sequence[DocumentServiceTable]]:
        """Obtiene los servicios asociados a múltiples documentos en una sola consulta."""
        if not document_ids:
            return {}

        try:
            document_id_column = DocumentServiceTable.__table__.c.document_id
            id_column = DocumentServiceTable.__table__.c.id
            query = select(DocumentServiceTable).where(document_id_column.in_(document_ids)).order_by(document_id_column, id_column)
            result = await self.session.exec(statement=query)
            grouped_services: defaultdict[int, list[DocumentServiceTable]] = defaultdict(list)
            for service_item in result.all():
                grouped_services[service_item.document_id].append(service_item)
            return dict(grouped_services)
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def search_contracts(  # noqa: PLR0913
        self,
        organization_id: int,
        client: str | None = None,
        contract_name: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        currency: str | None = None,
        state: str | None = None,
        document_type: str | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
        date_mode: str = "overlap",
        limit: int | None = None,
    ) -> Sequence[DocumentTable]:
        """Obtiene contratos aplicando filtros estructurados."""
        try:
            query = select(DocumentTable).order_by(DocumentTable.start_date, DocumentTable.end_date, DocumentTable.id)
            query = self._apply_contract_filters(
                query=query,
                organization_id=organization_id,
                client=client,
                contract_name=contract_name,
                min_value=min_value,
                max_value=max_value,
                currency=currency,
                state=state,
                document_type=document_type,
                period_start=period_start,
                period_end=period_end,
                date_mode=date_mode,
            )

            if limit is not None:
                query = query.limit(limit)

            result = await self.session.exec(statement=query)
            return result.all()
        except OperationalError as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def count_contracts(  # noqa: PLR0913
        self,
        organization_id: int,
        client: str | None = None,
        contract_name: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        currency: str | None = None,
        state: str | None = None,
        document_type: str | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
        date_mode: str = "overlap",
    ) -> int:
        """Cuenta contratos aplicando filtros estructurados."""
        try:
            query = select(func.count()).select_from(DocumentTable)
            query = self._apply_contract_filters(
                query=query,
                organization_id=organization_id,
                client=client,
                contract_name=contract_name,
                min_value=min_value,
                max_value=max_value,
                currency=currency,
                state=state,
                document_type=document_type,
                period_start=period_start,
                period_end=period_end,
                date_mode=date_mode,
            )
            result = await self.session.exec(statement=query)
            count = result.one()
            return int(count or 0)
        except OperationalError as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def replace_document_services(self, document_id: int, service_items: Sequence[DocumentServiceTable]) -> Sequence[DocumentServiceTable]:
        """Reemplaza el conjunto de servicios asociados a un documento."""
        try:
            document_id_column = DocumentServiceTable.__table__.c.document_id
            id_column = DocumentServiceTable.__table__.c.id
            await self.session.exec(delete(DocumentServiceTable).where(document_id_column == document_id))

            if service_items:
                self.session.add_all(service_items)

            await self.session.commit()

            result = await self.session.exec(select(DocumentServiceTable).where(document_id_column == document_id).order_by(id_column))
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            logger.debug(f"OperationalError replacing services for document {document_id}: {e}")
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.debug(f"SQLAlchemyError replacing services for document {document_id}: {e}")
            raise DocumentDatabaseError() from e

    async def get_services_by_ids(self, organization_id: int, service_ids: Sequence[int]) -> Sequence[ServiceTable]:
        """Obtiene los servicios existentes por sus IDs dentro de una organización."""
        if not service_ids:
            return []

        try:
            organization_id_column = ServiceTable.__table__.c.organization_id
            service_id_column = ServiceTable.__table__.c.id
            query = select(ServiceTable).where(organization_id_column == organization_id, service_id_column.in_(service_ids))
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e

    async def get_services(self, organization_id: int) -> Sequence[ServiceTable]:
        """Obtiene el catálogo de servicios de una organización."""
        try:
            organization_id_column = ServiceTable.__table__.c.organization_id
            name_column = ServiceTable.__table__.c.name
            id_column = ServiceTable.__table__.c.id
            query = select(ServiceTable).where(organization_id_column == organization_id).order_by(name_column, id_column)
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise DocumentDatabaseError() from e
