"""Composition helpers for the organizations module."""

from ..audit.application.services import UserActivityService
from ..users.application.repositories.user_repo import IUserRepository
from .application.repositories.base_organization import OrganizationRepository
from .application.repositories.provisioning import OrganizationProvisioningRepository
from .application.services import OrganizationMemberService, OrganizationProvisioningService, OrganizationService


def build_organization_service(repository: OrganizationRepository) -> OrganizationService:
    """Builds the organization service from its repository port."""
    return OrganizationService(repository=repository)


def build_organization_member_service(
    user_repository: IUserRepository,
    user_activity_service: UserActivityService | None = None,
) -> OrganizationMemberService:
    """Builds the organization member service from its user repository port."""
    return OrganizationMemberService(user_repository=user_repository, user_activity_service=user_activity_service)


def build_organization_provisioning_service(
    organization_repository: OrganizationRepository,
    user_repository: IUserRepository,
    provisioning_repository: OrganizationProvisioningRepository,
) -> OrganizationProvisioningService:
    """Builds the provisioning service used by superadmins."""
    return OrganizationProvisioningService(
        organization_repository=organization_repository,
        user_repository=user_repository,
        provisioning_repository=provisioning_repository,
    )
