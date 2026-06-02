"""Repository for managing chatbot token usage in the database."""

from collections.abc import Sequence

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.core.infrastructure.base import PostgresBaseRepository
from contractai_backend.modules.chatbot.domain.entities import ChatbotTokenUsage


class TokenUsageRepository(PostgresBaseRepository[ChatbotTokenUsage]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=ChatbotTokenUsage, session=session)

    async def get_by_conversation_id(self, conversation_id: int) -> Sequence[ChatbotTokenUsage]:
        query = (
            select(self.model)
            .where(self.model.conversation_id == conversation_id)
            .order_by(desc(column=self.model.created_at))
        )
        result = await self.session.exec(statement=query)
        return result.all()
