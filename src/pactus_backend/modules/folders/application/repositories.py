"""Repository contracts for the folders module."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from ...users.domain.entities import UserTable
from ...users.domain.value_objs import UserRole
from ..domain.entities import FolderTable


class FolderRepository(ABC):
    @abstractmethod
    async def get_all(self, filters: dict[str, Any] | None = None, limit: int | None = None, offset: int | None = None) -> Sequence[FolderTable]:
        """Lists folders matching optional filters with optional pagination."""
        pass

    @abstractmethod
    async def get_folders(self, organization_id: int, owner_roles: Sequence[UserRole] | None = None) -> Sequence[FolderTable]:
        """Lists folders for one organization, optionally filtered by owner role."""
        pass

    @abstractmethod
    async def get_folder_by_id(self, folder_id: int) -> FolderTable | None:
        """Returns a folder by id."""
        pass

    @abstractmethod
    async def get_folder_by_name(self, organization_id: int, owner_role: UserRole, name: str) -> FolderTable | None:
        """Returns a folder by normalized name and role scope."""
        pass

    @abstractmethod
    async def save_folder(self, entity: FolderTable) -> FolderTable:
        """Creates a new folder."""
        pass

    @abstractmethod
    async def update_folder(self, entity: FolderTable) -> FolderTable:
        """Persists changes to a folder."""
        pass

    @abstractmethod
    async def delete_folder(self, folder_id: int) -> bool:
        """Deletes a folder by id."""
        pass

    @abstractmethod
    async def count_documents_by_folder_ids(self, organization_id: int, folder_ids: Sequence[int]) -> dict[int, int]:
        """Counts documents assigned to each folder id."""
        pass

    @abstractmethod
    async def get_users_by_ids(self, user_ids: Sequence[int]) -> Sequence[UserTable]:
        """Returns users for the given ids."""
        pass
