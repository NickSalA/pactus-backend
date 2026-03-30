"""Provides structured contract queries for analytics-style use cases."""

from typing import Any

from ...domain import DocumentTable
from ..dto import ContractQueryDTO
from ..repositories import DocumentQueryRepository

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 50


class ContractQueryService:
    """Executes structured contract queries backed by the relational store."""

    def __init__(self, sql_repo: DocumentQueryRepository):
        self.sql_repo = sql_repo

    @staticmethod
    def _clamp_limit(limit: int | None) -> int:
        if limit is None:
            return DEFAULT_LIST_LIMIT
        return max(1, min(limit, MAX_LIST_LIMIT))

    @staticmethod
    def _serialize_contract(document: DocumentTable) -> dict[str, Any]:
        form_data = document.form_data if isinstance(document.form_data, dict) else {}

        return {
            "id": document.id,
            "name": document.name,
            "client": document.client,
            "type": document.type.value if hasattr(document.type, "value") else str(document.type),
            "state": document.state.value if hasattr(document.state, "value") else str(document.state),
            "start_date": document.start_date.isoformat(),
            "end_date": document.end_date.isoformat(),
            "value": form_data.get("value"),
            "currency": form_data.get("currency"),
            "file_name": document.file_name,
        }

    async def run_query(self, organization_id: int, query: ContractQueryDTO) -> dict[str, Any]:
        """Ejecuta una consulta estructurada sobre los contratos de la organización con los filtros y operación especificados."""
        if (query.min_value is not None or query.max_value is not None) and not query.currency:
            return {
                "status": "needs_clarification",
                "message": "Indique la moneda del monto a evaluar, por ejemplo USD, PEN o EUR.",
            }

        if query.period_start and query.period_end and query.period_start > query.period_end:
            return {
                "status": "invalid_request",
                "message": "La fecha inicial no puede ser posterior a la fecha final.",
            }

        resolved_limit = self._clamp_limit(query.limit)

        total_contracts = await self.sql_repo.count_contracts(
            organization_id=organization_id,
            query=ContractQueryDTO(operation=query.operation),
        )
        if total_contracts == 0:
            return {
                "status": "no_data",
                "message": "No hay contratos cargados para la organizacion actual.",
            }

        filtered_count = await self.sql_repo.count_contracts(organization_id=organization_id, query=query)

        response: dict[str, Any] = {
            "status": "success",
            "operation": query.operation,
            "count": filtered_count,
            "total_contracts_available": total_contracts,
            "filters_applied": {
                "client": query.client,
                "contract_name": query.contract_name,
                "min_value": query.min_value,
                "max_value": query.max_value,
                "currency": query.currency,
                "state": query.state,
                "document_type": query.document_type,
                "period_start": query.period_start.isoformat() if query.period_start else None,
                "period_end": query.period_end.isoformat() if query.period_end else None,
                "date_mode": query.date_mode,
            },
        }

        if query.operation == "count":
            return response

        documents = await self.sql_repo.search_contracts(organization_id=organization_id, query=query, limit=resolved_limit)
        response["items"] = [self._serialize_contract(document=document) for document in documents]
        response["returned_items"] = len(response["items"])
        response["limit"] = resolved_limit
        return response
