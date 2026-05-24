"""Repository contract for organization provisioning workflows."""

from abc import ABC, abstractmethod

from contractai_backend.modules.organizations.domain.entities import OrganizationTable


class OrganizationProvisioningRepository(ABC):
    """Persists an organization and its first admin in one transaction."""

    @abstractmethod
    async def create_organization_with_admin(self, *, name: str, admin_email: str) -> OrganizationTable:
        """Create an organization with an initial admin user."""
        pass
