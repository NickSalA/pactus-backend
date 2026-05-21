"""PostgreSQL implementation of the folder repository."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....core.infrastructure.sqlmodel_utils import RelationalHelpersMixin
from ...documents.domain import DocumentTable
from ...users.domain.entities import UserTable
from ...users.domain.value_objs import UserRole
from ..application.repositories import FolderRepository
from ..domain.entities import FolderTable
from ..domain.exceptions import FolderDatabaseError, FolderDatabaseUnavailableError


class SQLModelFolderRepository(RelationalHelpersMixin, FolderRepository):
    """Folder repository backed by PostgreSQL via SQLModel."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, filters: dict[str, Any] | None = None, limit: int | None = None, offset: int | None = None) -> Sequence[FolderTable]:
        try:
            query = select(FolderTable).order_by(col(FolderTable.id))
            if filters:
                for key, value in filters.items():
                    if hasattr(FolderTable, key):
                        query = query.where(col(getattr(FolderTable, key)) == value)
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise FolderDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise FolderDatabaseError() from e

    async def get_folders(self, organization_id: int, owner_roles: Sequence[UserRole] | None = None) -> Sequence[FolderTable]:
        try:
            query = select(FolderTable).where(col(FolderTable.organization_id) == organization_id)
            if owner_roles:
                query = query.where(col(FolderTable.owner_role).in_(owner_roles))
            query = query.order_by(col(FolderTable.name))
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise FolderDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise FolderDatabaseError() from e

    async def get_folder_by_id(self, folder_id: int) -> FolderTable | None:
        try:
            query = select(FolderTable).where(col(FolderTable.id) == folder_id)
            result = await self.session.exec(statement=query)
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise FolderDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise FolderDatabaseError() from e

    async def get_folder_by_name(self, organization_id: int, owner_role: UserRole, name: str) -> FolderTable | None:
        try:
            normalized_name = self._normalize_name(name)
            query = select(FolderTable).where(
                col(FolderTable.organization_id) == organization_id,
                col(FolderTable.owner_role) == owner_role,
                func.lower(col(FolderTable.name)) == normalized_name,
            )
            result = await self.session.exec(statement=query)
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise FolderDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise FolderDatabaseError() from e

    async def save_folder(self, entity: FolderTable) -> FolderTable:
        return await self._save_related_entity(entity, label="folder")

    async def update_folder(self, entity: FolderTable) -> FolderTable:
        return await self._update_related_entity(entity, label="folder")

    async def delete_folder(self, folder_id: int) -> bool:
        try:
            query = select(FolderTable).where(col(FolderTable.id) == folder_id)
            result = await self.session.exec(statement=query)
            folder = result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise FolderDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise FolderDatabaseError() from e
        if folder is None:
            return False
        return await self._delete_related_entity(folder, label="folder")

    async def count_documents_by_folder_ids(self, organization_id: int, folder_ids: Sequence[int]) -> dict[int, int]:
        if not folder_ids:
            return {}
        try:
            query = (
                select(DocumentTable.folder_id, func.count(DocumentTable.id))
                .where(
                    col(DocumentTable.organization_id) == organization_id,
                    col(DocumentTable.folder_id).in_(folder_ids),
                )
                .group_by(DocumentTable.folder_id)
            )
            result = await self.session.exec(statement=query)
            return {int(f_id): int(total or 0) for f_id, total in result.all()}
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise FolderDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise FolderDatabaseError() from e

    async def get_users_by_ids(self, user_ids: Sequence[int]) -> Sequence[UserTable]:
        if not user_ids:
            return []
        try:
            query = select(UserTable).where(col(UserTable.id).in_(user_ids))
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise FolderDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise FolderDatabaseError() from e
