"""PostgreSQL implementation of the notification rule repository."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any, cast

from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....core.exceptions.base import InternalServerError, ServiceUnavailableError
from ...documents.domain import DocumentTable
from ...documents.domain.value_objs import DocumentState
from ...users.domain.entities import UserTable
from ..application.dto import NotificationDocument, NotificationRecipient
from ..application.repositories import NotificationAlertRepository, NotificationRuleRepository
from ..domain import NotificationRuleTable
from ..domain.entities import NotificationSendLog
from ..domain.exceptions import NotificationDatabaseError, NotificationDatabaseUnavailableError


def _read_scalar_result(value: object) -> int:
    """Reads scalar values returned by SQLModel/SQLAlchemy result rows."""
    if hasattr(value, "_mapping"):
        mapping = cast(Any, value)._mapping
        if mapping:
            return int(next(iter(mapping.values())) or 0)

    if isinstance(value, tuple):
        first_value: Any = value[0] if value else 0
        return int(first_value or 0)

    scalar_value: Any = value
    return int(scalar_value or 0)


class SQLModelNotificationAlertRepository(NotificationAlertRepository):
    """Alert evaluation repository backed by PostgreSQL via SQLModel."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_document_states(self, organization_id: int) -> int:
        """Updates persisted contract states using the DB synchronization function."""
        try:
            result = await self.session.exec(
                cast(Any, text("select public.sync_document_states(:organization_id)")),
                params={"organization_id": organization_id},
            )
            return _read_scalar_result(result.one())
        except OperationalError as e:
            raise ServiceUnavailableError("La base de datos no está disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al sincronizar estados de contratos") from e

    async def get_active_organization_ids(self) -> list[int]:
        """Returns distinct organization IDs that have at least one active subscribed user."""
        try:
            result = await self.session.exec(
                select(UserTable.organization_id)
                .where(
                    col(UserTable.is_active).is_(True),
                    col(UserTable.receives_notifications).is_(True),
                )
                .distinct()
            )
            return list(result.all())
        except OperationalError as e:
            raise ServiceUnavailableError("La base de datos no está disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al consultar organizaciones activas") from e

    async def send_log_exists(self, organization_id: int, sent_date: date) -> bool:
        """Returns True if a send log entry already exists for this org and date."""
        try:
            result = await self.session.exec(
                select(NotificationSendLog).where(
                    NotificationSendLog.organization_id == organization_id,
                    NotificationSendLog.sent_date == sent_date,
                )
            )
            return result.first() is not None
        except SQLAlchemyError as e:
            raise InternalServerError("Error al consultar el log de envíos") from e

    async def record_send_log(self, organization_id: int, sent_date: date, emails_sent: int) -> None:
        """Records a send log entry and ignores duplicate daily runs."""
        try:
            log_entry = NotificationSendLog(
                organization_id=organization_id,
                sent_date=sent_date,
                emails_sent=emails_sent,
                created_at=datetime.now(UTC),
            )
            self.session.add(log_entry)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            logger.warning("Send log ya existe para org {} / {}. Ignorando.", organization_id, sent_date)
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise InternalServerError("Error al registrar el log de envío") from e

    async def get_active_rule_map(self, organization_id: int) -> tuple[dict[int, list[int]], list[int]]:
        """Returns active rules grouped by document and organization defaults."""
        try:
            result = await self.session.exec(
                select(NotificationRuleTable)
                .where(
                    NotificationRuleTable.organization_id == organization_id,
                    col(NotificationRuleTable.is_active).is_(True),
                )
                .order_by(col(NotificationRuleTable.document_id), col(NotificationRuleTable.days_before_due).desc())
            )
            rules = list(result.all())
        except OperationalError as e:
            raise ServiceUnavailableError("La base de datos no está disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al consultar reglas de notificación") from e

        rules_by_document: dict[int, list[int]] = defaultdict(list)
        organization_default_days: list[int] = []

        for rule in rules:
            if rule.document_id is None:
                organization_default_days.append(rule.days_before_due)
                continue
            rules_by_document[rule.document_id].append(rule.days_before_due)

        deduped_rules = {document_id: sorted(set(days), reverse=True) for document_id, days in rules_by_document.items()}
        return deduped_rules, sorted(set(organization_default_days), reverse=True)

    async def get_documents_for_notification_evaluation(self, organization_id: int, today: date) -> list[NotificationDocument]:
        """Returns active documents ending today or later for notification evaluation."""
        try:
            result = await self.session.exec(
                select(DocumentTable).where(
                    DocumentTable.organization_id == organization_id,
                    col(DocumentTable.state).in_([DocumentState.ACTIVE, DocumentState.EXPIRING_SOON]),
                    col(DocumentTable.end_date) >= today,
                )
            )
            return [
                NotificationDocument(id=document.id, type=document.type, end_date=document.end_date, file_name=document.file_name)
                for document in result.all()
                if document.end_date is not None
            ]
        except OperationalError as e:
            raise ServiceUnavailableError("La base de datos no está disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al consultar contratos") from e

    async def get_notification_recipients(self, organization_id: int) -> list[NotificationRecipient]:
        """Returns active users subscribed to contract notifications."""
        try:
            result = await self.session.exec(
                select(UserTable).where(
                    UserTable.organization_id == organization_id,
                    col(UserTable.is_active).is_(True),
                    col(UserTable.receives_notifications).is_(True),
                )
            )
            return [
                NotificationRecipient(
                    id=user.id,
                    organization_id=user.organization_id,
                    email=user.email,
                    full_name=user.full_name,
                    is_active=user.is_active,
                    receives_notifications=user.receives_notifications,
                )
                for user in result.all()
            ]
        except OperationalError as e:
            raise ServiceUnavailableError("La base de datos no está disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al consultar usuarios") from e


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
