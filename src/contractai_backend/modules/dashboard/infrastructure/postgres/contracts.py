"""General contract queries and synchronization for dashboard analytics."""

from collections.abc import Sequence
from typing import Any
from typing import cast as type_cast

from sqlalchemy import desc, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col

from .....core.exceptions.base import InternalServerError, ServiceUnavailableError
from ....documents.domain import DocumentTable
from ....documents.domain.value_objs import DocumentType
from ...application.repositories import DashboardContractSummary
from .helpers import DashboardRepositoryProtocol


class DashboardContractQueriesMixin:
    """Query mixin for retrieving recent contracts and syncing state records."""

    async def sync_contract_states(self: DashboardRepositoryProtocol, organization_id: int) -> int:
        """Synchronizes document states before dashboard reads."""
        try:
            result = await self.session.exec(
                type_cast(Any, text("select public.sync_document_states(:organization_id)")),
                params={"organization_id": organization_id},
            )
            return self._read_scalar_result(result.one())
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al sincronizar estados de contratos") from e

    async def list_recent_contracts(
        self: DashboardRepositoryProtocol,
        organization_id: int,
        document_type: DocumentType,
        limit: int,
    ) -> Sequence[DashboardContractSummary]:
        """Lists recently updated contracts."""
        try:
            statement = (
                self._contract_summary_select(document_type=document_type)
                .where(*self._base_contract_filters(organization_id=organization_id))
                .order_by(desc(col(DocumentTable.updated_at)), desc(col(DocumentTable.created_at)), col(DocumentTable.id))
                .limit(limit)
            )
            result = await self.session.exec(statement=statement)
            return [self._serialize_contract_row(row) for row in result.all()]
        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise ServiceUnavailableError("La base de datos no esta disponible") from e
        except SQLAlchemyError as e:
            raise InternalServerError("Error al listar contratos recientes") from e
