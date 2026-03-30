"""BaseRepository: Clase genérica para manejar operaciones CRUD con SQLModel y AsyncSession."""

from collections.abc import Sequence
from typing import Any

from loguru import logger
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError, TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import asc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.exceptions.base import ConflictError, InternalServerError, ServiceUnavailableError
from ..application.base import BaseRepository
from ..domain.base import BaseTable


class PostgresBaseRepository[T: BaseTable](BaseRepository[T]):
    def __init__(self, session: AsyncSession, model: type[T]):
        """Receives the SQLModel table class and the database session.

        Args:
        - model: Class that represents the database table (Infra)
        - session: Database session for executing queries
        .
        """
        self.session: AsyncSession = session
        self.model: type[T] = model

    async def get_by_id(self, id: int) -> T | None:
        """Obtiene una entidad por su ID. Devuelve None si no existe."""
        try:
            query = select(self.model).where(self.model.id == id)
            result = await self.session.exec(statement=query)
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al acceder a la base de datos relacional") from e

    async def save(self, entity: T) -> T:
        """Crea un nuevo registro en la base de datos a partir de la entidad. Devuelve la entidad creada con su ID asignado."""
        obj = entity if isinstance(entity, self.model) else self.model.model_validate(obj=entity)
        try:
            self.session.add(instance=obj)
            await self.session.commit()
            await self.session.refresh(instance=obj)
            return obj
        except IntegrityError as e:
            await self.session.rollback()
            logger.debug(f"IntegrityError al guardar {self.model.__name__}: {e}")
            raise ConflictError("Conflicto al crear el registro en la base de datos relacional") from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            logger.debug(f"OperationalError al guardar {self.model.__name__}: {e}")
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.debug(f"SQLAlchemyError al guardar {self.model.__name__}: {e}")
            raise InternalServerError("Error al acceder a la base de datos relacional") from e

    async def get_all(self, filters: dict[str, Any] | None = None) -> Sequence[T]:
        """Lista entidades, opcionalmente filtrando por campos específicos."""
        try:
            query = select(self.model).order_by(asc(column=self.model.id))
            if filters:
                for field, value in filters.items():
                    query = query.where(getattr(self.model, field) == value)
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al acceder a la base de datos relacional") from e

    async def update(self, entity: T) -> T:
        """Actualiza el registro existente con los datos de la entidad. Devuelve la entidad actualizada."""
        try:
            db_merged = await self.session.merge(instance=entity)
            await self.session.commit()
            await self.session.refresh(instance=db_merged)
            return db_merged
        except IntegrityError as e:
            await self.session.rollback()
            raise ConflictError("Conflicto al actualizar el registro en la base de datos relacional") from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise InternalServerError("Error al acceder a la base de datos relacional") from e

    async def delete(self, id: int) -> bool:
        """Elimina el registro y devuelve True si tuvo éxito."""
        try:
            db_obj = await self.get_by_id(id)
            if not db_obj:
                return False

            await self.session.delete(instance=db_obj)
            await self.session.commit()
            return True
        except IntegrityError as e:
            await self.session.rollback()
            raise ConflictError("Conflicto al eliminar el registro en la base de datos relacional") from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise InternalServerError("Error al acceder a la base de datos relacional") from e
