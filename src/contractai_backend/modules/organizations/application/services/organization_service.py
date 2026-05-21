"""Application service for organizations."""

from collections.abc import Sequence

from contractai_backend.modules.organizations.application.dto import OrganizationCreateRequest, OrganizationUpdateRequest
from contractai_backend.modules.organizations.application.repositories.base_organization import OrganizationRepository
from contractai_backend.modules.organizations.domain.entities import OrganizationTable
from contractai_backend.modules.organizations.domain.exceptions import OrganizationAlreadyExistsError, OrganizationNotFoundError


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

    async def create_organization(self, payload: OrganizationCreateRequest) -> OrganizationTable:
        """Creates a new organization."""
        existing: OrganizationTable | None = await self.repository.get_by_name(payload.name)
        if existing:
            raise OrganizationAlreadyExistsError()

        organization = OrganizationTable(**payload.model_dump())
        return await self.repository.save(organization)

    async def update_organization(self, organization_id: int, payload: OrganizationUpdateRequest) -> OrganizationTable:
        """Updates an existing organization."""
        organization: OrganizationTable = await self.get_organization(organization_id)

        if payload.name is not None and payload.name != organization.name:
            existing: OrganizationTable | None = await self.repository.get_by_name(payload.name)
            if existing:
                raise OrganizationAlreadyExistsError()

        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(organization, key, value)

        return await self.repository.update(organization)

    async def delete_organization(self, organization_id: int) -> OrganizationTable:
        """Soft deletes an organization."""
        organization: OrganizationTable = await self.get_organization(organization_id)
        organization.is_active = False
        return await self.repository.update(organization)
