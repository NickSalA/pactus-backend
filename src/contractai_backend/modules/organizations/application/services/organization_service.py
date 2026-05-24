"""Application service for organizations."""

from collections.abc import Sequence

from contractai_backend.core.exceptions.base import ConflictError
from contractai_backend.modules.organizations.application.dto import (
    OrganizationProvisionRequest,
    OrganizationUpdateRequest,
)
from contractai_backend.modules.organizations.application.repositories.base_organization import OrganizationRepository
from contractai_backend.modules.organizations.application.repositories.provisioning import OrganizationProvisioningRepository
from contractai_backend.modules.organizations.domain.entities import OrganizationTable
from contractai_backend.modules.organizations.domain.exceptions import OrganizationAlreadyExistsError, OrganizationNotFoundError
from contractai_backend.modules.users.application.repositories.user_repo import IUserRepository


class OrganizationService:
    """Provides a minimal application facade for organizations."""

    def __init__(self, repository: OrganizationRepository):
        self.repository = repository

    async def list_organizations(
        self,
        is_active: bool | None = None,
        name: str | None = None,
        ruc: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Sequence[OrganizationTable]:
        """Lists organizations with optional filtering and pagination."""
        filters = {}
        if is_active is not None:
            filters["is_active"] = is_active
        if name is not None:
            filters["name"] = name
        if ruc is not None:
            filters["ruc"] = ruc

        return await self.repository.get_all(filters=filters or None, limit=limit, offset=offset)

    async def get_organization(self, organization_id: int) -> OrganizationTable:
        """Fetches one organization by ID, raising if not found."""
        organization: OrganizationTable | None = await self.repository.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundError()
        return organization

    async def update_organization(self, organization_id: int, payload: OrganizationUpdateRequest) -> OrganizationTable:
        """Updates an existing organization."""
        organization: OrganizationTable = await self.get_organization(organization_id)

        if payload.name is not None and payload.name != organization.name:
            existing: OrganizationTable | None = await self.repository.get_by_name(payload.name)
            if existing:
                raise OrganizationAlreadyExistsError()

        if payload.ruc is not None and payload.ruc != organization.ruc:
            existing_by_ruc = await self.repository.get_by_ruc(payload.ruc)
            if existing_by_ruc:
                raise OrganizationAlreadyExistsError("Ya existe una organización con ese RUC.")

        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(organization, key, value)

        return await self.repository.update(organization)

    async def delete_organization(self, organization_id: int) -> OrganizationTable:
        """Soft deletes an organization."""
        organization: OrganizationTable = await self.get_organization(organization_id)
        organization.is_active = False
        return await self.repository.update(organization)


class OrganizationProvisioningService:
    """Creates organizations and their first admin from the superadmin flow."""

    def __init__(
        self,
        organization_repository: OrganizationRepository,
        user_repository: IUserRepository,
        provisioning_repository: OrganizationProvisioningRepository,
    ):
        self.organization_repository = organization_repository
        self.user_repository = user_repository
        self.provisioning_repository = provisioning_repository

    async def provision_organization(self, payload: OrganizationProvisionRequest) -> OrganizationTable:
        """Creates a new organization and registers its first admin user."""
        existing_organization = await self.organization_repository.get_by_name(payload.name)
        if existing_organization:
            raise OrganizationAlreadyExistsError()

        existing_user = await self.user_repository.get_by_email(payload.admin_email)
        if existing_user:
            raise ConflictError("Ya existe un usuario con ese correo")

        return await self.provisioning_repository.create_organization_with_admin(name=payload.name, admin_email=payload.admin_email)
