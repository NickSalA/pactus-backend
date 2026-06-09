"""PostgreSQL repositories for audit records."""

from collections.abc import Sequence

from sqlalchemy import Column, Integer, MetaData, String, Table, desc
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.core.domain.db_schemas import CHATBOT_SCHEMA
from contractai_backend.core.exceptions.base import ConflictError, InternalServerError, ServiceUnavailableError
from contractai_backend.modules.audit.application.repositories import ChatbotActivityRepository, UserActivityRepository
from contractai_backend.modules.audit.application.repositories.chatbot_activity_repo import ChatbotActivityWithConversationTitle
from contractai_backend.modules.audit.domain.entities import ChatbotActivityTable, UserActivityTable

CONVERSATIONS_TABLE = Table(
    "conversations",
    MetaData(),
    Column("id", Integer),
    Column("title", String),
    schema=CHATBOT_SCHEMA,
)


class SQLModelUserActivityRepository(UserActivityRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(self, activity: UserActivityTable) -> UserActivityTable:
        try:
            self.session.add(instance=activity)
            await self.session.commit()
            await self.session.refresh(instance=activity)
            return activity
        except IntegrityError as e:
            await self.session.rollback()
            raise ConflictError("Conflicto al registrar auditoria de usuario") from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise InternalServerError("Error al registrar auditoria de usuario") from e

    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[UserActivityTable]:
        try:
            query = (
                select(UserActivityTable)
                .where(UserActivityTable.organization_id == organization_id)
                .order_by(desc(UserActivityTable.created_at), desc(UserActivityTable.id))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar auditoria de usuario") from e


class SQLModelChatbotActivityRepository(ChatbotActivityRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(self, activity: ChatbotActivityTable) -> ChatbotActivityTable:
        try:
            self.session.add(instance=activity)
            await self.session.commit()
            await self.session.refresh(instance=activity)
            return activity
        except IntegrityError as e:
            await self.session.rollback()
            raise ConflictError("Conflicto al registrar auditoria de chatbot") from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise InternalServerError("Error al registrar auditoria de chatbot") from e

    async def list_by_organization(self, *, organization_id: int, limit: int, offset: int) -> Sequence[ChatbotActivityWithConversationTitle]:
        try:
            query = (
                select(ChatbotActivityTable, CONVERSATIONS_TABLE.c.title)
                .outerjoin(CONVERSATIONS_TABLE, CONVERSATIONS_TABLE.c.id == ChatbotActivityTable.conversation_id)
                .where(ChatbotActivityTable.organization_id == organization_id)
                .order_by(desc(ChatbotActivityTable.created_at), desc(ChatbotActivityTable.id))
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.exec(statement=query)
            return result.all()
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar auditoria de chatbot") from e
