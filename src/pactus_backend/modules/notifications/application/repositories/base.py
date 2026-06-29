"""Relational repository contracts for the notifications module."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from ...domain import NotificationRuleTable
from ..dto import NotificationDocument, NotificationRecipient


class EmailSender(Protocol):
    """Port for sending notification emails."""

    async def send_email(self, to: str, subject: str, html_body: str) -> None:
        """Sends one HTML email."""
        ...


class NotificationAlertRepository(ABC):
    """Repository contract for alert evaluation and cron send tracking."""

    @abstractmethod
    async def sync_document_states(self, organization_id: int) -> int:
        """Synchronizes persisted contract states for one organization."""
        pass

    @abstractmethod
    async def get_active_organization_ids(self) -> list[int]:
        """Returns organizations with active subscribed users."""
        pass

    @abstractmethod
    async def send_log_exists(self, organization_id: int, sent_date: date) -> bool:
        """Returns whether a send log already exists for the org and date."""
        pass

    @abstractmethod
    async def record_send_log(self, organization_id: int, sent_date: date, emails_sent: int) -> None:
        """Records that an organization was processed by the daily cron."""
        pass

    @abstractmethod
    async def get_active_rule_map(self, organization_id: int) -> tuple[dict[int, list[int]], list[int]]:
        """Returns document-scoped and organization default active notification rules."""
        pass

    @abstractmethod
    async def get_documents_for_notification_evaluation(self, organization_id: int, today: date) -> list[NotificationDocument]:
        """Returns active documents that can trigger notifications."""
        pass

    @abstractmethod
    async def get_notification_recipients(self, organization_id: int) -> list[NotificationRecipient]:
        """Returns active users subscribed to notifications."""
        pass


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
