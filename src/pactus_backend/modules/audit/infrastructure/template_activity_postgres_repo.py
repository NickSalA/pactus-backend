"""PostgreSQL repository for template activity audit records."""

from collections.abc import Sequence

from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....core.exceptions.base import ConflictError, InternalServerError, ServiceUnavailableError
from ....modules.audit.application.repositories import TemplateActivityRepository
from ....modules.audit.domain.entities import TemplateActivityTable


class SQLModelTemplateActivityRepository(TemplateActivityRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(self, activity: TemplateActivityTable) -> TemplateActivityTable:
        try:
            self.session.add(instance=activity)
            await self.session.commit()
            await self.session.refresh(instance=activity)
            return activity
        except IntegrityError as e:
            await self.session.rollback()
            raise ConflictError("Conflicto al registrar auditoria de plantilla") from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise InternalServerError("Error al registrar auditoria de plantilla") from e

    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[TemplateActivityTable]:
        try:
            query = (
                select(TemplateActivityTable)
                .where(TemplateActivityTable.organization_id == organization_id)
                .order_by(desc(col(TemplateActivityTable.created_at)), desc(col(TemplateActivityTable.id)))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar auditoria de plantilla") from e
