"""PostgreSQL repository for contract activity audit records."""

from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.core.exceptions.base import ConflictError, InternalServerError, ServiceUnavailableError
from contractai_backend.modules.audit.application.repositories import ContractActivityRepository
from contractai_backend.modules.audit.domain.entities import ContractActivityTable


class SQLModelContractActivityRepository(ContractActivityRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(self, activity: ContractActivityTable) -> ContractActivityTable:
        try:
            self.session.add(instance=activity)
            await self.session.commit()
            await self.session.refresh(instance=activity)
            return activity
        except IntegrityError as e:
            await self.session.rollback()
            raise ConflictError("Conflicto al registrar auditoria de contrato") from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise InternalServerError("Error al registrar auditoria de contrato") from e

    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[ContractActivityTable]:
        try:
            query = (
                select(ContractActivityTable)
                .where(ContractActivityTable.organization_id == organization_id)
                .order_by(desc(ContractActivityTable.created_at), desc(ContractActivityTable.id))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar auditoria de contratos") from e
