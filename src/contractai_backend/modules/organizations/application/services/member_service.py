"""Application service for organization member management."""

from collections.abc import Sequence

from contractai_backend.core.exceptions.base import ConflictError, ForbiddenError, NotFoundError
from contractai_backend.modules.users.application.repositories.user_repo import IUserRepository
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


class OrganizationMemberService:
    """Handles admin operations over organization members."""

    def __init__(self, user_repository: IUserRepository):
        self.user_repository = user_repository

    @staticmethod
    def _ensure_admin(user: UserTable) -> None:
        if user.role != UserRole.ADMIN:
            raise ForbiddenError("Solo los administradores pueden gestionar usuarios de la organización")

    async def list_members(self, current_user: UserTable) -> Sequence[UserTable]:
        """Lists all users belonging to the admin's organization."""
        self._ensure_admin(current_user)
        return await self.user_repository.get_all(filters={"organization_id": current_user.organization_id})

    async def add_member(self, current_user: UserTable, email: str, role: UserRole) -> UserTable:
        """Creates a new organization member or updates a pending user in the same organization."""
        self._ensure_admin(current_user)

        normalized_email = email.strip().lower()
        existing_user = await self.user_repository.get_by_email(normalized_email)
        if existing_user is not None:
            if existing_user.organization_id != current_user.organization_id:
                raise ConflictError("El usuario ya pertenece a otra organización")
            if existing_user.is_active and existing_user.supabase_user_id is not None:
                raise ConflictError("El usuario ya fue agregado a esta organización")

            existing_user.role = role
            existing_user.is_active = True
            return await self.user_repository.update(existing_user)

        new_user = UserTable(
            organization_id=current_user.organization_id,
            email=normalized_email,
            role=role,
            is_active=True,
        )
        return await self.user_repository.save(new_user)

    async def update_member_role(self, current_user: UserTable, member_id: int, role: UserRole) -> UserTable:
        """Updates the role of an existing user within the same organization."""
        self._ensure_admin(current_user)

        member = await self.user_repository.get_by_id(member_id)
        if member is None or member.organization_id != current_user.organization_id:
            raise NotFoundError("El usuario solicitado no existe en la organización actual")

        member.role = role
        return await self.user_repository.update(member)

    async def update_member_notifications(self, current_user: UserTable, member_id: int, receives_notifications: bool) -> UserTable:
        """Updates whether an existing user receives expiration notifications."""
        self._ensure_admin(current_user)

        member = await self.user_repository.get_by_id(member_id)
        if member is None or member.organization_id != current_user.organization_id:
            raise NotFoundError("El usuario solicitado no existe en la organización actual")

        member.receives_notifications = receives_notifications
        return await self.user_repository.update(member)
