"""Service layer for managing notification rules."""

from datetime import UTC, datetime

from .....core.domain.access import ensure_admin
from .....core.exceptions.base import ConflictError, NotFoundError
from ....users.domain.entities import UserTable
from ...api.schemas import NotificationRuleCreateRequest, NotificationRuleResponse, NotificationRuleUpdateRequest
from ...application.repositories import NotificationRuleRepository
from ...domain import NotificationRuleTable


class NotificationRuleService:
    """Handles CRUD operations for notification rules."""

    def __init__(self, rule_repo: NotificationRuleRepository):
        self.rule_repo = rule_repo

    @staticmethod
    def _serialize(rule: NotificationRuleTable) -> NotificationRuleResponse:
        return NotificationRuleResponse.model_validate(rule)

    async def _ensure_document_belongs_to_org(self, organization_id: int, document_id: int | None) -> None:
        if document_id is None:
            return

        if not await self.rule_repo.document_exists_in_org(organization_id, document_id):
            raise NotFoundError("El documento solicitado no existe en la organización actual")

    async def _ensure_rule_uniqueness(
        self,
        organization_id: int,
        document_id: int | None,
        days_before_due: int,
        *,
        exclude_rule_id: int | None = None,
    ) -> None:
        existing = await self.rule_repo.get_rule_by_scope(organization_id, document_id, days_before_due)
        if existing is not None and existing.id != exclude_rule_id:
            raise ConflictError("Ya existe una regla con ese vencimiento para el mismo alcance")

    async def list_rules(self, current_user: UserTable) -> list[NotificationRuleResponse]:
        """Lists notification rules for the current organization."""
        ensure_admin(current_user, "Solo los administradores pueden gestionar reglas de notificación")
        rules = await self.rule_repo.get_rules(current_user.organization_id)
        return [self._serialize(rule) for rule in rules]

    async def create_rule(self, current_user: UserTable, data: NotificationRuleCreateRequest) -> NotificationRuleResponse:
        """Creates a notification rule for the current organization."""
        ensure_admin(current_user, "Solo los administradores pueden gestionar reglas de notificación")
        await self._ensure_document_belongs_to_org(current_user.organization_id, data.document_id)
        await self._ensure_rule_uniqueness(current_user.organization_id, data.document_id, data.days_before_due)

        rule = await self.rule_repo.save_rule(
            NotificationRuleTable(
                organization_id=current_user.organization_id,
                document_id=data.document_id,
                days_before_due=data.days_before_due,
                is_active=data.is_active,
            )
        )
        return self._serialize(rule)

    async def update_rule(
        self,
        current_user: UserTable,
        rule_id: int,
        data: NotificationRuleUpdateRequest,
    ) -> NotificationRuleResponse:
        """Updates one notification rule inside the current organization."""
        ensure_admin(current_user, "Solo los administradores pueden gestionar reglas de notificación")
        rule = await self.rule_repo.get_rule_by_id(current_user.organization_id, rule_id)
        if rule is None:
            raise NotFoundError("La regla solicitada no existe en la organización actual")

        next_days_before_due = data.days_before_due if data.days_before_due is not None else rule.days_before_due
        await self._ensure_rule_uniqueness(
            current_user.organization_id,
            rule.document_id,
            next_days_before_due,
            exclude_rule_id=rule.id,
        )

        if data.days_before_due is not None:
            rule.days_before_due = data.days_before_due
        if data.is_active is not None:
            rule.is_active = data.is_active

        rule.updated_at = datetime.now(UTC)
        updated_rule = await self.rule_repo.update_rule(rule)
        return self._serialize(updated_rule)

    async def delete_rule(self, current_user: UserTable, rule_id: int) -> None:
        """Deletes one notification rule inside the current organization."""
        ensure_admin(current_user, "Solo los administradores pueden gestionar reglas de notificación")
        rule = await self.rule_repo.get_rule_by_id(current_user.organization_id, rule_id)
        if rule is None:
            raise NotFoundError("La regla solicitada no existe en la organización actual")

        await self.rule_repo.delete_rule(rule)
