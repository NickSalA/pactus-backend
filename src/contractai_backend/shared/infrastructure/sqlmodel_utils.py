"""Shared utilities for SQLModel-based repositories."""

from typing import Any, cast

from loguru import logger
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel.ext.asyncio.session import AsyncSession

# Note: We don't import module-specific exceptions here to avoid circular dependencies.
# Classes using this mixin should define an 'error_map' if they need specific exception translation,
# or handle it in their own methods.
# For now, we keep it simple and generic, or allow the caller to pass labels.

class RelationalHelpersMixin:
    """Shared CRUD helpers reused across module repositories.

    Requires that `self.session` is an ``AsyncSession`` instance.
    """

    session: AsyncSession

    @staticmethod
    def _normalize_text_filter(value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = value.strip().lower()
        return cleaned or None

    @staticmethod
    def _normalize_name(value: str) -> str:
        return value.strip().lower()

    @staticmethod
    def _read_scalar_result(value: object) -> int:
        if hasattr(value, "_mapping"):
            mapping = cast(Any, value)._mapping
            if mapping:
                return int(next(iter(mapping.values())) or 0)

        if isinstance(value, tuple):
            first_value: Any = value[0] if value else 0
            return int(first_value or 0)

        scalar_value: Any = value
        return int(scalar_value or 0)

    async def _handle_db_error(self, e: Exception, label: str, operation: str):
        """Standard logging and rollback for DB errors."""
        await self.session.rollback()
        if isinstance(e, IntegrityError):
            logger.debug(f"IntegrityError {operation} {label}: {e}")
        elif isinstance(e, (SQLAlchemyTimeoutError, OperationalError)):
            logger.debug(f"OperationalError {operation} {label}: {e}")
        else:
            logger.debug(f"SQLAlchemyError {operation} {label}: {e}")
        # Exceptions are re-raised to be caught by specific repos which know their domain exceptions
        raise e

    async def _save_related_entity(self, entity, *, label: str):
        try:
            self.session.add(entity)
            await self.session.commit()
            await self.session.refresh(entity)
            return entity
        except Exception as e:
            await self._handle_db_error(e, label, "saving")
            raise

    async def _update_related_entity(self, entity, *, label: str):
        try:
            merged_entity = await self.session.merge(instance=entity)
            await self.session.commit()
            await self.session.refresh(merged_entity)
            return merged_entity
        except Exception as e:
            await self._handle_db_error(e, label, "updating")
            raise

    async def _delete_related_entity(self, entity, *, label: str) -> bool:
        try:
            await self.session.delete(instance=entity)
            await self.session.commit()
            return True
        except Exception as e:
            await self._handle_db_error(e, label, "deleting")
            raise
