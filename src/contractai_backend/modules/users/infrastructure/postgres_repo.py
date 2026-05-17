"""Módulo de repositorio de usuarios utilizando SQLModel y PostgreSQL."""

from sqlalchemy import func
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.core.exceptions.base import InternalServerError, ServiceUnavailableError
from contractai_backend.core.infrastructure.base import PostgresBaseRepository
from contractai_backend.modules.users.application.repositories.user_repo import IUserRepository
from contractai_backend.modules.users.domain.entities import UserTable


class SQLModelUserRepository(PostgresBaseRepository[UserTable], IUserRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session=session, model=UserTable)

    async def get_by_email(self, email: str) -> UserTable | None:
        """Obtiene un usuario por su email. Devuelve None si no se encuentra."""
        query = select(self.model).where(func.lower(self.model.email) == email.strip().lower())
        try:
            result = await self.session.exec(query)
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos relacional no está disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al acceder a la base de datos relacional") from e
