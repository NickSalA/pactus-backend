"""Contract origin analytics queries for dashboard."""

from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlmodel import col, select

from ....documents.domain import DocumentTable, LaborContractTable
from ...domain.exceptions import DashboardDatabaseError, DashboardDatabaseUnavailableError
from .helpers import DashboardRepositoryProtocol


class DashboardOriginQueriesMixin:
    """Query mixin for contract origin and creation type distribution."""

    async def get_contract_origin_distribution(
        self: DashboardRepositoryProtocol,
        organization_id: int,
    ) -> list[dict[str, Any]]:
        """Queries and aggregates counts of labor contracts by their creation origin type."""
        try:
            statement = (
                select(
                    col(DocumentTable.type).label("origin_type"),
                    func.count(col(DocumentTable.id)).label("count"),
                )
                .join(LaborContractTable, col(LaborContractTable.document_id) == col(DocumentTable.id))
                .where(col(DocumentTable.organization_id) == organization_id)
                .group_by(col(DocumentTable.type))
            )

            result = await self.session.exec(statement)
            rows = result.all()

            total_contracts = sum(int(r.count or 0) for r in rows)
            if total_contracts == 0:
                return []

            # Aggregates raw counts per mapped category
            aggregated: dict[str, int] = {}
            for r in rows:
                raw_type = r.origin_type
                mapped_label = DashboardOriginQueriesMixin._map_origin_label(raw_type)
                aggregated[mapped_label] = aggregated.get(mapped_label, 0) + int(r.count or 0)

            # Sort by count desc
            sorted_distribution = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)

            return [
                {
                    "origin_type": label,
                    "count": count,
                    "percentage": round((float(count) / total_contracts) * 100.0, 2),
                }
                for label, count in sorted_distribution
            ]

        except (SQLAlchemyTimeoutError, OperationalError) as e:
            raise DashboardDatabaseUnavailableError("El servicio de base de datos no está disponible.") from e
        except SQLAlchemyError as e:
            raise DashboardDatabaseError("Error interno al procesar la distribución de origen de contratos.") from e

    @staticmethod
    def _map_origin_label(raw_type: str | None) -> str:
        """Translates a raw type field into a highly readable origin category."""
        if not raw_type:
            return "Carga Manual"

        raw_lower = raw_type.lower().strip()
        if raw_lower == "manual_upload":
            return "Carga Manual"
        if raw_lower == "google_drive":
            return "Importación: Google Drive"
        if raw_lower == "onedrive":
            return "Importación: OneDrive"
        if raw_lower == "dropbox":
            return "Importación: Dropbox"
        if raw_lower in ("company", "labor"):
            # Safe boundary for legacy fallback
            return "Carga Manual"

        # Treat as Template format code and format it beautifully
        formatted_name = raw_type.replace("_", " ").strip().title()
        return f"Plantilla: {formatted_name}"
