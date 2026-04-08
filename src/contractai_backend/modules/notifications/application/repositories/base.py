"""Relational repository contracts for the notifications module."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from ...domain import NotificationRuleTable


class NotificationRuleRepository(ABC):
    @abstractmethod
    async def get_rules(self, organization_id: int) -> Sequence[NotificationRuleTable]:
        """Lists notification rules for one organization."""
        pass

    @abstractmethod
    async def get_rule_by_id(self, organization_id: int, rule_id: int) -> NotificationRuleTable | None:
        """Returns a rule by its id within an organization."""
        pass

    @abstractmethod
    async def get_rule_by_scope(
        self,
        organization_id: int,
        document_id: int | None,
        days_before_due: int,
    ) -> NotificationRuleTable | None:
        """Returns a rule matching the exact scope (document + days_before_due)."""
        pass

    @abstractmethod
    async def document_exists_in_org(self, organization_id: int, document_id: int) -> bool:
        """Checks whether a document belongs to the given organization."""
        pass

    @abstractmethod
    async def save_rule(self, entity: NotificationRuleTable) -> NotificationRuleTable:
        """Creates a new notification rule."""
        pass

    @abstractmethod
    async def update_rule(self, entity: NotificationRuleTable) -> NotificationRuleTable:
        """Persists changes to a notification rule."""
        pass

    @abstractmethod
    async def delete_rule(self, entity: NotificationRuleTable) -> None:
        """Deletes a notification rule."""
        pass
