"""Dependency injection for the service catalog module."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ....shared.infrastructure.database import get_session
from ..application.services import ServiceCatalogService
from ..composition import build_service_catalog_service
from ..infrastructure.postgres_repo import SQLModelServiceRepository


async def get_service_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> SQLModelServiceRepository:
    """Provides a SQLModel implementation of the service repository."""
    return SQLModelServiceRepository(session=session)


async def get_service_catalog_service(
    repo: Annotated[SQLModelServiceRepository, Depends(get_service_repository)]
) -> ServiceCatalogService:
    """Provides an instance of the service catalog service."""
    return build_service_catalog_service(repository=repo)
