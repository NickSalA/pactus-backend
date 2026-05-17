"""PostgreSQL implementation of the service catalog repository."""

from collections.abc import Sequence

from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....shared.infrastructure.sqlmodel_utils import RelationalHelpersMixin
from ...documents.domain import CompanyContractServiceTable, CompanyContractTable, DocumentTable
from ..application.repositories import ServiceRepository
from ..domain.entities import ServiceTable
from ..domain.exceptions import ServiceDatabaseError, ServiceDatabaseUnavailableError


class SQLModelServiceRepository(RelationalHelpersMixin, ServiceRepository):
    """Service catalog repository backed by PostgreSQL via SQLModel."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_services_by_ids(self, organization_id: int, service_ids: Sequence[int]) -> Sequence[ServiceTable]:
        if not service_ids:
            return []
        try:
            query = select(ServiceTable).where(
                col(ServiceTable.organization_id) == organization_id,
                col(ServiceTable.id).in_(service_ids),
                col(ServiceTable.is_active).is_(True),
            )
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise ServiceDatabaseError() from e

    async def get_services(self, organization_id: int, *, include_inactive: bool = False) -> Sequence[ServiceTable]:
        try:
            query = select(ServiceTable).where(col(ServiceTable.organization_id) == organization_id)
            if not include_inactive:
                query = query.where(col(ServiceTable.is_active).is_(True))
            query = query.order_by(col(ServiceTable.name), col(ServiceTable.id))
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise ServiceDatabaseError() from e

    async def get_service_by_id(self, organization_id: int, service_id: int) -> ServiceTable | None:
        try:
            query = select(ServiceTable).where(
                col(ServiceTable.organization_id) == organization_id,
                col(ServiceTable.id) == service_id,
            )
            result = await self.session.exec(statement=query)
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise ServiceDatabaseError() from e

    async def get_service_by_name(self, organization_id: int, name: str) -> ServiceTable | None:
        try:
            normalized_name = self._normalize_name(name)
            query = select(ServiceTable).where(
                col(ServiceTable.organization_id) == organization_id,
                func.lower(col(ServiceTable.name)) == normalized_name,
            )
            result = await self.session.exec(statement=query)
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise ServiceDatabaseError() from e

    async def save_service(self, entity: ServiceTable) -> ServiceTable:
        return await self._save_related_entity(entity, label="service")

    async def update_service(self, entity: ServiceTable) -> ServiceTable:
        return await self._update_related_entity(entity, label="service")

    async def delete_service(self, service_id: int) -> bool:
        try:
            query = select(ServiceTable).where(col(ServiceTable.id) == service_id)
            result = await self.session.exec(statement=query)
            service = result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise ServiceDatabaseError() from e
        if service is None:
            return False
        return await self._delete_related_entity(service, label="service")

    async def count_documents_by_service_ids(self, organization_id: int, service_ids: Sequence[int]) -> dict[int, int]:
        if not service_ids:
            return {}
        try:
            query = (
                select(CompanyContractServiceTable.service_id, func.count(func.distinct(CompanyContractTable.document_id)))
                .join(CompanyContractTable, col(CompanyContractTable.id) == col(CompanyContractServiceTable.company_contract_id))
                .join(DocumentTable, col(DocumentTable.id) == col(CompanyContractTable.document_id))
                .where(
                    col(DocumentTable.organization_id) == organization_id,
                    col(CompanyContractServiceTable.service_id).in_(service_ids),
                )
                .group_by(col(CompanyContractServiceTable.service_id))
            )
            result = await self.session.exec(statement=query)
            return {int(service_id): int(total or 0) for service_id, total in result.all()}
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise ServiceDatabaseError() from e
