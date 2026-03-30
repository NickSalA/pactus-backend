"""Application service for organizations."""

from collections.abc import Sequence

from contractai_backend.core.exceptions.base import NotFoundError
from contractai_backend.modules.organizations.application.repositories.base_organization import OrganizationRepository
from contractai_backend.modules.organizations.domain.entities import OrganizationTable


class OrganizationService:
    """Provides a minimal application facade for organizations."""

    def __init__(self, repository: OrganizationRepository):
        self.repository = repository

    async def list_organizations(self, active_only: bool = False) -> Sequence[OrganizationTable]:
        """Lists organizations, optionally filtering only active ones."""
        organizations = await (self.repository.get_active() if active_only else self.repository.get_all())
        return organizations

    async def get_organization(self, organization_id: int) -> OrganizationTable:
        """Fetches one organization by ID, raising if not found."""
        organization = await self.repository.get_by_id(organization_id)
        if organization is None:
            raise NotFoundError("La organización solicitada no existe.")
        return organization
