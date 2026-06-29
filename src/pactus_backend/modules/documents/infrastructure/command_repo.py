"""PostgreSQL implementation of document command repositories."""

from collections.abc import Sequence

from loguru import logger
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....core.infrastructure.base import PostgresBaseRepository
from ....core.infrastructure.sqlmodel_utils import RelationalHelpersMixin
from ..application.repositories import DocumentCommandRepository
from ..domain import CompanyContractServiceTable, CompanyContractTable, DocumentTable, LaborContractTable
from ..domain.exceptions import DocumentDatabaseError, DocumentDatabaseUnavailableError


class SQLModelDocumentCommandRepository(
    RelationalHelpersMixin,
    PostgresBaseRepository[DocumentTable],
    DocumentCommandRepository,
):
    """Document repository for command operations via SQLModel."""

    def __init__(self, session: AsyncSession):
        super().__init__(model=DocumentTable, session=session)

    async def _get_company_contract(self, document_id: int) -> CompanyContractTable | None:
        result = await self.session.exec(select(CompanyContractTable).where(col(CompanyContractTable.document_id) == document_id))
        return result.first()

    async def _get_labor_contract(self, document_id: int) -> LaborContractTable | None:
        result = await self.session.exec(select(LaborContractTable).where(col(LaborContractTable.document_id) == document_id))
        return result.first()

    async def upsert_company_contract(self, entity: CompanyContractTable) -> CompanyContractTable:
        """Creates or updates company-specific data for a document."""
        try:
            existing = await self._get_company_contract(document_id=entity.document_id)
            if existing is None:
                self.session.add(entity)
                await self.session.commit()
                await self.session.refresh(entity)
                return entity

            existing.ruc = entity.ruc
            existing.client = entity.client
            existing.updated_at = entity.updated_at
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise DocumentDatabaseError() from e

    async def upsert_labor_contract(self, entity: LaborContractTable) -> LaborContractTable:
        """Creates or updates labor-specific data for a document."""
        try:
            existing = await self._get_labor_contract(document_id=entity.document_id)
            if existing is None:
                self.session.add(entity)
                await self.session.commit()
                await self.session.refresh(entity)
                return entity

            existing.worker_name = entity.worker_name
            existing.worker_document_number = entity.worker_document_number
            existing.position = entity.position
            existing.salary_value = entity.salary_value
            existing.salary_currency = entity.salary_currency
            existing.salary_periodicity = entity.salary_periodicity
            existing.contract_modality = entity.contract_modality
            existing.updated_at = entity.updated_at
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise DocumentDatabaseError() from e

    async def replace_document_services(
        self, doc_id: int, service_items: Sequence[CompanyContractServiceTable]
    ) -> Sequence[CompanyContractServiceTable]:
        """Reemplaza el conjunto de servicios asociados a un documento."""
        try:
            company_contract = await self._get_company_contract(document_id=doc_id)
            if company_contract is None or company_contract.id is None:
                return []

            await self.session.exec(
                delete(CompanyContractServiceTable).where(col(CompanyContractServiceTable.company_contract_id) == company_contract.id)
            )

            if service_items:
                self.session.add_all(service_items)

            await self.session.commit()
            query = (
                select(CompanyContractServiceTable)
                .where(col(CompanyContractServiceTable.company_contract_id) == company_contract.id)
                .order_by(col(CompanyContractServiceTable.id))
            )
            result = await self.session.exec(statement=query)
            return result.all()

        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            logger.debug(f"OperationalError replacing services for document {doc_id}: {e}")
            raise DocumentDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.debug(f"SQLAlchemyError replacing services for document {doc_id}: {e}")
            raise DocumentDatabaseError() from e
