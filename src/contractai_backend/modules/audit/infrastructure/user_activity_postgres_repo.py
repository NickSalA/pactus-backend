"""PostgreSQL repository for user activity audit records."""

from collections.abc import Sequence

from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.core.exceptions.base import ConflictError, InternalServerError, ServiceUnavailableError
from contractai_backend.modules.audit.application.repositories import UserActivityRepository
from contractai_backend.modules.audit.domain.entities import UserActivityTable


class SQLModelUserActivityRepository(UserActivityRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(self, activity: UserActivityTable) -> UserActivityTable:
        try:
            self.session.add(instance=activity)
            await self.session.commit()
            await self.session.refresh(instance=activity)
            return activity
        except IntegrityError as e:
            await self.session.rollback()
            raise ConflictError("Conflicto al registrar auditoria de usuario") from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise InternalServerError("Error al registrar auditoria de usuario") from e

    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[UserActivityTable]:
        try:
            query = (
                select(UserActivityTable)
                .where(UserActivityTable.organization_id == organization_id)
                .order_by(desc(col(UserActivityTable.created_at)), desc(col(UserActivityTable.id)))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar auditoria de usuario") from e
