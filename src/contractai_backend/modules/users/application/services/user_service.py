"""Módulo de servicio para la gestión de usuarios."""

from ....audit.application.services import UserActivityService
from ...domain.entities import UserTable
from ...domain.exceptions import UserNotFoundError
from ..dto.user_request import UserUpdateRequest
from ..repositories.user_repo import IUserRepository


class UserService:
    """Application service for user management."""

    def __init__(self, repo: IUserRepository, user_activity_service: UserActivityService | None = None) -> None:
        self.repo = repo
        self.user_activity_service = user_activity_service

    async def update_user(self, user_id: int, request: UserUpdateRequest, actor: UserTable | None = None) -> UserTable:
        """Updates a user's role."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()

        previous_role = user.role
        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)

        updated_user = await self.repo.update(user)
        if actor and self.user_activity_service and "role" in update_data and previous_role != updated_user.role:
            await self.user_activity_service.record_updated(actor=actor, target=updated_user, previous_role=previous_role)
        return updated_user

    async def soft_delete_user(self, user_id: int, actor: UserTable | None = None) -> None:
        """Soft deletes a user by setting is_active to False."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()

        user.is_active = False
        updated_user = await self.repo.update(user)
        if actor and self.user_activity_service:
            await self.user_activity_service.record_deleted(actor=actor, target=updated_user)
