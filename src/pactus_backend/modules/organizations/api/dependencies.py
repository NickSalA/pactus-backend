"""Dependency providers for organizations."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ....modules.audit.application.services import UserActivityService
from ....modules.audit.composition import build_default_user_activity_service
from ....modules.organizations.application.repositories.base_organization import OrganizationRepository
from ....modules.organizations.application.repositories.provisioning import OrganizationProvisioningRepository
from ....modules.organizations.application.services import (
    OrganizationMemberService,
    OrganizationProvisioningService,
    OrganizationService,
)
from ....modules.organizations.composition import (
    build_organization_member_service,
    build_organization_provisioning_service,
    build_organization_service,
)
from ....modules.organizations.infrastructure.postgres_repo import (
    SQLModelOrganizationProvisioningRepository,
    SQLModelOrganizationRepository,
)
from ....modules.users.application.repositories.user_repo import IUserRepository
from ....modules.users.infrastructure.postgres_repo import SQLModelUserRepository
from ....shared.infrastructure.database import get_session


async def get_organization_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> OrganizationRepository:
    """Provide the concrete organization repository."""
    return SQLModelOrganizationRepository(session=session)


async def get_organization_service(
    repository: Annotated[OrganizationRepository, Depends(get_organization_repository)],
) -> OrganizationService:
    """Provide the organizations application service."""
    return build_organization_service(repository=repository)


async def get_organization_provisioning_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> OrganizationProvisioningRepository:
    """Provide the transactional repository for provisioning organizations."""
    return SQLModelOrganizationProvisioningRepository(session=session)


async def get_user_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> IUserRepository:
    """Provide the concrete user repository required for member operations."""
    return SQLModelUserRepository(session=session)


async def get_organization_member_service(
    user_repository: Annotated[IUserRepository, Depends(get_user_repository)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationMemberService:
    """Provide the organization member application service."""
    user_activity_service: UserActivityService = build_default_user_activity_service(session=session)
    return build_organization_member_service(user_repository=user_repository, user_activity_service=user_activity_service)


async def get_organization_provisioning_service(
    organization_repository: Annotated[OrganizationRepository, Depends(get_organization_repository)],
    user_repository: Annotated[IUserRepository, Depends(get_user_repository)],
    provisioning_repository: Annotated[OrganizationProvisioningRepository, Depends(get_organization_provisioning_repository)],
) -> OrganizationProvisioningService:
    """Provide the superadmin organization provisioning service."""
    return build_organization_provisioning_service(
        organization_repository=organization_repository,
        user_repository=user_repository,
        provisioning_repository=provisioning_repository,
    )
