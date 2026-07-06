from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....core.exceptions.base import ConflictError, InternalServerError, ServiceUnavailableError
from ....core.infrastructure.base import PostgresBaseRepository
from ....modules.organizations.application.repositories.base_organization import OrganizationRepository
from ....modules.organizations.application.repositories.provisioning import OrganizationProvisioningRepository
from ....modules.organizations.domain.entities import OrganizationTable
from ....modules.users.domain.entities import UserTable
from ....modules.users.domain.value_objs import UserRole


class SQLModelOrganizationRepository(PostgresBaseRepository[OrganizationTable], OrganizationRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session=session, model=OrganizationTable)

    async def get_by_name(self, name: str) -> OrganizationTable | None:
        query = select(self.model).where(func.lower(self.model.name) == name.strip().lower())
        result = await self.session.exec(query)
        return result.first()

    async def get_by_ruc(self, ruc: str) -> OrganizationTable | None:
        query = select(self.model).where(self.model.ruc == ruc.strip())
        result = await self.session.exec(query)
        return result.first()


class SQLModelOrganizationProvisioningRepository(OrganizationProvisioningRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_organization_with_admin(self, *, name: str, admin_email: str) -> OrganizationTable:
        organization = OrganizationTable(name=name)
        try:
            self.session.add(instance=organization)
            await self.session.flush()

            admin = UserTable(
                organization_id=organization.id,
                email=admin_email,
                role=UserRole.ADMIN,
                is_active=True,
            )
            self.session.add(instance=admin)

            await self.session.commit()
            await self.session.refresh(instance=organization)
            return organization
        except IntegrityError as e:
            await self.session.rollback()
            raise ConflictError("Conflicto al crear la organizacion o el administrador") from e
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            await self.session.rollback()
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from e
        except SQLAlchemyError as e:
            await self.session.rollback()
            raise InternalServerError("Error al acceder a la base de datos relacional") from e
