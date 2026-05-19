"""Composition helpers for the organizations module."""

from ..users.application.repositories.user_repo import IUserRepository
from .application.repositories.base_organization import OrganizationRepository
from .application.services import OrganizationMemberService, OrganizationService


def build_organization_service(repository: OrganizationRepository) -> OrganizationService:
    """Builds the organization service from its repository port."""
    return OrganizationService(repository=repository)


def build_organization_member_service(user_repository: IUserRepository) -> OrganizationMemberService:
    """Builds the organization member service from its user repository port."""
    return OrganizationMemberService(user_repository=user_repository)
