"""Base repository interface defining common CRUD operations for entities."""


from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any


class BaseRepository[T](ABC):
    @abstractmethod
    async def get_by_id(self, id: int) -> T | None:
        """Retrieves an entity by its ID. Returns None if not found."""
        pass

    @abstractmethod
    async def get_all(self, filters: dict[str, Any] | None = None, limit: int | None = None, offset: int | None = None) -> Sequence[T]:
        """Returns a sequence of all entities, optionally filtered and paginated."""
        pass

    @abstractmethod
    async def save(self, entity: T) -> T:
        """Saves an entity and returns the saved instance (with ID if applicable)."""
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Update an entity by its ID. Returns the updated entity."""
        pass

    @abstractmethod
    async def delete(self, id: int) -> bool:
        """Deletes an entity by its ID. Returns True if deletion was successful."""
        pass
