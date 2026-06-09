"""Application service for user activity auditing."""

from collections.abc import Sequence

from contractai_backend.modules.audit.application.repositories import UserActivityRepository
from contractai_backend.modules.audit.domain.entities import UserActivityTable
from contractai_backend.modules.audit.domain.value_objs import AuditUserAction
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


class UserActivityService:
    """Records and lists user-management audit activity."""

    def __init__(self, repository: UserActivityRepository) -> None:
        self.repository = repository

    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[UserActivityTable]:
        return await self.repository.list_by_organization(organization_id=organization_id, limit=limit, offset=offset)

    async def record_created(self, *, actor: UserTable, target: UserTable) -> UserActivityTable:
        return await self._record(action=AuditUserAction.CREATED, actor=actor, target=target, previous_role=None, role=target.role)

    async def record_updated(
        self,
        *,
        actor: UserTable,
        target: UserTable,
        previous_role: UserRole | str | None,
    ) -> UserActivityTable:
        return await self._record(action=AuditUserAction.UPDATED, actor=actor, target=target, previous_role=previous_role, role=target.role)

    async def record_deleted(self, *, actor: UserTable, target: UserTable) -> UserActivityTable:
        return await self._record(action=AuditUserAction.DELETED, actor=actor, target=target, previous_role=target.role, role=target.role)

    async def _record(
        self,
        *,
        action: AuditUserAction,
        actor: UserTable,
        target: UserTable,
        previous_role: UserRole | str | None,
        role: UserRole | str | None,
    ) -> UserActivityTable:
        activity = UserActivityTable(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            actor_name=actor.full_name or actor.email,
            actor_role=str(actor.role),
            action=action,
            target_user_id=target.id,
            target_user_email=target.email,
            target_user_name=target.full_name,
            previous_role=str(previous_role) if previous_role is not None else None,
            role=str(role) if role is not None else None,
        )
        return await self.repository.record(activity)
