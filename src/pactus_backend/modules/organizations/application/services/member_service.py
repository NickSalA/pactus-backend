"""Application service for organization member management."""

from collections.abc import Sequence

from .....core.exceptions.base import ConflictError, ForbiddenError, NotFoundError
from .....modules.audit.application.services import UserActivityService
from .....modules.users.application.repositories.user_repo import IUserRepository
from .....modules.users.domain.entities import UserTable
from .....modules.users.domain.value_objs import UserRole


class OrganizationMemberService:
    """Handles admin operations over organization members."""

    def __init__(self, user_repository: IUserRepository, user_activity_service: UserActivityService | None = None):
        self.user_repository: IUserRepository = user_repository
        self.user_activity_service = user_activity_service

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

            previous_role = existing_user.role
            existing_user.role = role
            existing_user.is_active = True
            updated_user = await self.user_repository.update(existing_user)
            if self.user_activity_service:
                await self.user_activity_service.record_updated(actor=current_user, target=updated_user, previous_role=previous_role)
            return updated_user

        new_user = UserTable(
            organization_id=current_user.organization_id,
            email=normalized_email,
            role=role,
            is_active=True,
        )
        created_user = await self.user_repository.save(new_user)
        if self.user_activity_service:
            await self.user_activity_service.record_created(actor=current_user, target=created_user)
        return created_user

    async def update_member_role(self, current_user: UserTable, member_id: int, role: UserRole) -> UserTable:
        """Updates the role of an existing user within the same organization."""
        self._ensure_admin(current_user)

        member = await self.user_repository.get_by_id(member_id)
        if member is None or member.organization_id != current_user.organization_id:
            raise NotFoundError("El usuario solicitado no existe en la organización actual")

        previous_role = member.role
        member.role = role
        updated_member = await self.user_repository.update(member)
        if self.user_activity_service:
            await self.user_activity_service.record_updated(actor=current_user, target=updated_member, previous_role=previous_role)
        return updated_member

    async def update_member_notifications(self, current_user: UserTable, member_id: int, receives_notifications: bool) -> UserTable:
        """Updates whether an existing user receives expiration notifications."""
        self._ensure_admin(current_user)

        member = await self.user_repository.get_by_id(member_id)
        if member is None or member.organization_id != current_user.organization_id:
            raise NotFoundError("El usuario solicitado no existe en la organización actual")

        member.receives_notifications = receives_notifications
        return await self.user_repository.update(member)
