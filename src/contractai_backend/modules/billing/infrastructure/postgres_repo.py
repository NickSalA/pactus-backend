"""Postgres repositories for billing provisioning workflows."""

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.core.exceptions.base import ConflictError, InternalServerError, ServiceUnavailableError
from contractai_backend.modules.billing.application.repositories import BillingProvisioningRepository
from contractai_backend.modules.organizations.domain.entities import OrganizationTable
from contractai_backend.modules.users.domain.entities import UserTable
from contractai_backend.modules.users.domain.value_objs import UserRole


class SQLModelBillingProvisioningRepository(BillingProvisioningRepository):
    """SQLModel implementation for subscription-driven provisioning."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_organization_by_paypal_subscription_id(self, subscription_id: str) -> OrganizationTable | None:
        query = select(OrganizationTable).where(OrganizationTable.paypal_subscription_id == subscription_id.strip())
        try:
            result = await self.session.exec(query)
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as exc:
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from exc
        except SQLAlchemyError as exc:
            raise InternalServerError("Error al acceder a la base de datos relacional") from exc

    async def get_user_by_email(self, email: str) -> UserTable | None:
        query = select(UserTable).where(func.lower(UserTable.email) == email.strip().lower())
        try:
            result = await self.session.exec(query)
            return result.first()
        except (SQLAlchemyTimeoutError, OperationalError) as exc:
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from exc
        except SQLAlchemyError as exc:
            raise InternalServerError("Error al acceder a la base de datos relacional") from exc

    async def create_pending_organization_with_admin(
        self,
        *,
        admin_email: str,
        organization_name: str,
        paypal_subscription_id: str,
    ) -> OrganizationTable:
        organization = OrganizationTable(name=organization_name, paypal_subscription_id=paypal_subscription_id)
        try:
            self.session.add(instance=organization)
            await self.session.flush()

            if organization.id is None:
                raise InternalServerError("No se pudo crear la organización.")

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
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Conflicto al crear la organización o el administrador") from exc
        except (SQLAlchemyTimeoutError, OperationalError) as exc:
            await self.session.rollback()
            raise ServiceUnavailableError("La base de datos relacional no esta disponible") from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise InternalServerError("Error al acceder a la base de datos relacional") from exc
