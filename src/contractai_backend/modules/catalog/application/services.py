"""Service for operations related to the service catalog."""

from collections.abc import Sequence
from datetime import UTC, datetime

from ....core.domain.access import ensure_admin
from ....core.exceptions.base import ConflictError, NotFoundError
from ...users.domain.entities import UserTable
from ..api.schemas import ServiceCreateRequest, ServiceResponse, ServiceUpdateRequest
from ..domain.entities import ServiceTable
from .repositories import ServiceRepository


class ServiceCatalogService:
    def __init__(self, sql_repo: ServiceRepository):
        """Stores the repo used to query services."""
        self.sql_repo = sql_repo

    @staticmethod
    def _serialize(service: ServiceTable, documents_count: int = 0) -> ServiceResponse:
        return ServiceResponse(
            id=service.id,
            name=service.name,
            is_active=service.is_active,
            documents_count=documents_count,
            created_at=service.created_at,
            updated_at=service.updated_at,
        )

    async def list_services(
        self,
        organization_id: int,
        *,
        include_inactive: bool = False,
    ) -> Sequence[ServiceResponse]:
        """Lists services available for the organization."""
        services = await self.sql_repo.get_services(organization_id=organization_id, include_inactive=include_inactive)
        usage_counts = await self.sql_repo.count_documents_by_service_ids(
            organization_id=organization_id,
            service_ids=[service.id for service in services if service.id is not None],
        )
        return [self._serialize(service, usage_counts.get(service.id, 0)) for service in services if service.id is not None]

    async def create_service(self, current_user: UserTable, data: ServiceCreateRequest) -> ServiceResponse:
        """Creates a new service for the current organization."""
        ensure_admin(current_user, "Solo los administradores pueden gestionar servicios")

        existing = await self.sql_repo.get_service_by_name(current_user.organization_id, data.name)
        if existing is not None:
            raise ConflictError("Ya existe un servicio con ese nombre en la organización")

        service = await self.sql_repo.save_service(
            ServiceTable(
                organization_id=current_user.organization_id,
                name=data.name,
                is_active=data.is_active,
            )
        )
        return self._serialize(service)

    async def update_service(
        self,
        current_user: UserTable,
        service_id: int,
        data: ServiceUpdateRequest,
    ) -> ServiceResponse:
        """Updates one service inside the current organization."""
        ensure_admin(current_user, "Solo los administradores pueden gestionar servicios")

        service = await self.sql_repo.get_service_by_id(current_user.organization_id, service_id)
        if service is None:
            raise NotFoundError("El servicio solicitado no existe en la organización actual")

        if data.name is not None and data.name.lower() != service.name.lower():
            existing = await self.sql_repo.get_service_by_name(current_user.organization_id, data.name)
            if existing is not None and existing.id != service.id:
                raise ConflictError("Ya existe un servicio con ese nombre en la organización")
            service.name = data.name

        if data.is_active is not None:
            service.is_active = data.is_active

        service.updated_at = datetime.now(UTC)
        updated_service = await self.sql_repo.update_service(service)
        usage_counts = await self.sql_repo.count_documents_by_service_ids(
            organization_id=current_user.organization_id,
            service_ids=[updated_service.id] if updated_service.id is not None else [],
        )
        return self._serialize(updated_service, usage_counts.get(updated_service.id, 0))

    async def delete_service(self, current_user: UserTable, service_id: int) -> None:
        """Deletes a service when it is not referenced by any contract."""
        ensure_admin(current_user, "Solo los administradores pueden gestionar servicios")

        service = await self.sql_repo.get_service_by_id(current_user.organization_id, service_id)
        if service is None:
            raise NotFoundError("El servicio solicitado no existe en la organización actual")

        usage_counts = await self.sql_repo.count_documents_by_service_ids(
            organization_id=current_user.organization_id,
            service_ids=[service_id],
        )
        if usage_counts.get(service_id, 0) > 0:
            raise ConflictError("No se puede eliminar un servicio asociado a contratos existentes")

        deleted = await self.sql_repo.delete_service(service_id)
        if not deleted:
            raise NotFoundError("El servicio solicitado no existe en la organización actual")
