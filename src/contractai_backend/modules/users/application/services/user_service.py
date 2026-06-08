"""Módulo de servicio para la gestión de usuarios."""

from ...domain.entities import UserTable
from ...domain.exceptions import UserNotFoundError
from ..dto.user_request import UserUpdateRequest
from ..repositories.user_repo import IUserRepository


class UserService:
    """Application service for user management."""

    def __init__(self, repo: IUserRepository) -> None:
        self.repo = repo

    async def update_user(self, user_id: int, request: UserUpdateRequest) -> UserTable:
        """Updates a user's role."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()

        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)

        return await self.repo.update(user)

    async def soft_delete_user(self, user_id: int) -> None:
        """Soft deletes a user by setting is_active to False."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()

        user.is_active = False
        await self.repo.update(user)

