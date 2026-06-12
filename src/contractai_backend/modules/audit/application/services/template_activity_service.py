"""Application service for template activity auditing."""

from collections.abc import Sequence

from contractai_backend.modules.audit.application.repositories import TemplateActivityRepository
from contractai_backend.modules.audit.domain.entities import TemplateActivityTable
from contractai_backend.modules.audit.domain.value_objs import AuditTemplateAction
from contractai_backend.modules.templates.domain.entities import TemplateTable
from contractai_backend.modules.users.domain.entities import UserTable


class TemplateActivityService:
    """Records and lists template-management audit activity."""

    def __init__(self, repository: TemplateActivityRepository) -> None:
        self.repository = repository

    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[TemplateActivityTable]:
        return await self.repository.list_by_organization(organization_id=organization_id, limit=limit, offset=offset)

    async def record_created(self, *, actor: UserTable, template: TemplateTable) -> TemplateActivityTable:
        return await self._record(
            action=AuditTemplateAction.CREATED,
            actor=actor,
            template=template,
            previous_state=None,
            state=str(template.state.value) if template.state else None,
        )

    async def record_updated(
        self,
        *,
        actor: UserTable,
        template: TemplateTable,
        previous_state: str | None,
    ) -> TemplateActivityTable:
        return await self._record(
            action=AuditTemplateAction.UPDATED,
            actor=actor,
            template=template,
            previous_state=previous_state,
            state=str(template.state.value) if template.state else None,
        )

    async def record_deleted(self, *, actor: UserTable, template: TemplateTable) -> TemplateActivityTable:
        return await self._record(
            action=AuditTemplateAction.DELETED,
            actor=actor,
            template=template,
            previous_state=str(template.state.value) if template.state else None,
            state=None,
        )

    async def record_archived(self, *, actor: UserTable, template: TemplateTable, previous_state: str | None) -> TemplateActivityTable:
        return await self._record(
            action=AuditTemplateAction.ARCHIVED,
            actor=actor,
            template=template,
            previous_state=previous_state,
            state=str(template.state.value) if template.state else None,
        )

    async def _record(
        self,
        *,
        action: AuditTemplateAction,
        actor: UserTable,
        template: TemplateTable,
        previous_state: str | None,
        state: str | None,
    ) -> TemplateActivityTable:
        activity = TemplateActivityTable(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            actor_name=actor.full_name or actor.email,
            actor_role=str(actor.role),
            action=action,
            template_id=template.id,
            template_format_id=template.template_format_id,
            template_name=template.name,
            document_type=str(template.document_type.value) if template.document_type else None,
            previous_state=previous_state,
            state=state,
        )
        return await self.repository.record(activity)
