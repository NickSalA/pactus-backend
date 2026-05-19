"""Composition helpers for the catalog module."""

from sqlmodel.ext.asyncio.session import AsyncSession

from .application.repositories import ServiceRepository
from .application.services import ServiceCatalogService
from .infrastructure.postgres_repo import SQLModelServiceRepository


def build_service_catalog_service(repository: ServiceRepository) -> ServiceCatalogService:
    """Builds the service catalog application service."""
    return ServiceCatalogService(sql_repo=repository)


def build_default_service_repository(session: AsyncSession) -> ServiceRepository:
    """Builds the default SQL service repository."""
    return SQLModelServiceRepository(session=session)
