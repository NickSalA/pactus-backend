"""Organization repository backed by SQLModel."""

from collections.abc import Sequence

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.core.infrastructure.base import PostgresBaseRepository
from contractai_backend.modules.organizations.application.repositories.base_organization import OrganizationRepository
from contractai_backend.modules.organizations.domain.entities import OrganizationTable


class SQLModelOrganizationRepository(PostgresBaseRepository[OrganizationTable], OrganizationRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session=session, model=OrganizationTable)

    async def get_by_name(self, name: str) -> OrganizationTable | None:
        query = select(self.model).where(func.lower(self.model.name) == name.strip().lower())
        result = await self.session.exec(query)
        return result.first()

    async def get_active(self) -> Sequence[OrganizationTable]:
        query = select(self.model).where(col(self.model.is_active).is_(True)).order_by(col(self.model.id))
        result = await self.session.exec(query)
        return result.all()
