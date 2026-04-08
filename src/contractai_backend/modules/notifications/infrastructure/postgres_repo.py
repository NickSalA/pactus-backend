"""PostgreSQL implementation of the notification rule repository."""

from collections.abc import Sequence

from loguru import logger
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...documents.domain import DocumentTable
from ..application.repositories import NotificationRuleRepository
from ..domain import NotificationRuleTable
from ..domain.exceptions import NotificationDatabaseError, NotificationDatabaseUnavailableError


class SQLModelNotificationRuleRepository(NotificationRuleRepository):
    """Notification rule repository backed by PostgreSQL via SQLModel."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_rules(self, organization_id: int) -> Sequence[NotificationRuleTable]:
        """Lists notification rules for one organization."""
        try:
            query = (
                select(NotificationRuleTable)
                .where(col(NotificationRuleTable.organization_id) == organization_id)
                .order_by(
                    col(NotificationRuleTable.document_id),
                    col(NotificationRuleTable.days_before_due),
                    col(NotificationRuleTable.id),
                )
            )
            result = await self.session.exec(query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise NotificationDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise NotificationDatabaseError() from e

    async def get_rule_by_id(self, organization_id: int, rule_id: int) -> NotificationRuleTable | None:
        """Returns a rule by its id within an organization."""
        try:
            result = await self.session.exec(
                select(NotificationRuleTable).where(
                    col(NotificationRuleTable.organization_id) == organization_id,
                    col(NotificationRuleTable.id) == rule_id,
                )
            )
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise NotificationDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise NotificationDatabaseError() from e

    async def get_rule_by_scope(
        self,
        organization_id: int,
        document_id: int | None,
        days_before_due: int,
    ) -> NotificationRuleTable | None:
        """Returns a rule matching the exact scope (document + days_before_due)."""
        try:
            query = select(NotificationRuleTable).where(
                col(NotificationRuleTable.organization_id) == organization_id,
                col(NotificationRuleTable.days_before_due) == days_before_due,
            )
            if document_id is None:
                query = query.where(col(NotificationRuleTable.document_id).is_(None))
            else:
                query = query.where(col(NotificationRuleTable.document_id) == document_id)

            result = await self.session.exec(query)
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise NotificationDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise NotificationDatabaseError() from e

    async def document_exists_in_org(self, organization_id: int, document_id: int) -> bool:
        """Checks whether a document belongs to the given organization."""
        try:
            result = await self.session.exec(
                select(DocumentTable).where(
                    col(DocumentTable.organization_id) == organization_id,
                    col(DocumentTable.id) == document_id,
                )
            )
            return result.first() is not None
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise NotificationDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            raise NotificationDatabaseError() from e

    async def save_rule(self, entity: NotificationRuleTable) -> NotificationRuleTable:
        """Creates a new notification rule."""
        try:
            self.session.add(entity)
            await self.session.commit()
            await self.session.refresh(entity)
            return entity
        except IntegrityError as e:
            await self.session.rollback()
            logger.debug(f"IntegrityError saving notification rule: {e}")
            raise NotificationDatabaseError() from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            logger.debug(f"OperationalError saving notification rule: {e}")
            raise NotificationDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.debug(f"SQLAlchemyError saving notification rule: {e}")
            raise NotificationDatabaseError() from e

    async def update_rule(self, entity: NotificationRuleTable) -> NotificationRuleTable:
        """Persists changes to a notification rule."""
        try:
            merged = await self.session.merge(instance=entity)
            await self.session.commit()
            await self.session.refresh(merged)
            return merged
        except IntegrityError as e:
            await self.session.rollback()
            logger.debug(f"IntegrityError updating notification rule {entity.id}: {e}")
            raise NotificationDatabaseError() from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            logger.debug(f"OperationalError updating notification rule {entity.id}: {e}")
            raise NotificationDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.debug(f"SQLAlchemyError updating notification rule {entity.id}: {e}")
            raise NotificationDatabaseError() from e

    async def delete_rule(self, entity: NotificationRuleTable) -> None:
        """Deletes a notification rule."""
        try:
            await self.session.delete(instance=entity)
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            logger.debug(f"IntegrityError deleting notification rule {entity.id}: {e}")
            raise NotificationDatabaseError() from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            logger.debug(f"OperationalError deleting notification rule {entity.id}: {e}")
            raise NotificationDatabaseUnavailableError() from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.debug(f"SQLAlchemyError deleting notification rule {entity.id}: {e}")
            raise NotificationDatabaseError() from e
