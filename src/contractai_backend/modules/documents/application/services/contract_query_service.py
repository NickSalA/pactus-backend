"""Provides structured contract queries for analytics-style use cases."""

from collections.abc import Sequence
from datetime import date
from typing import Any

from ...domain import DocumentServiceTable, DocumentTable
from ..dto import ContractQueryDTO
from ..repositories import DocumentQueryRepository, ServiceCatalogRepository

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 50


class ContractQueryService:
    """Executes structured contract queries backed by the relational store."""

    def __init__(self, sql_repo: DocumentQueryRepository, service_repo: ServiceCatalogRepository | None = None):
        self.sql_repo = sql_repo
        self.service_repo = service_repo or sql_repo

    @staticmethod
    def _clamp_limit(limit: int | None) -> int:
        if limit is None:
            return DEFAULT_LIST_LIMIT
        return max(1, min(limit, MAX_LIST_LIMIT))

    @staticmethod
    def _is_currently_active(document: DocumentTable, today: date) -> bool:
        return document.start_date <= today <= document.end_date

    @staticmethod
    def _serialize_service_item(
        service_item: DocumentServiceTable,
        service_names: dict[int, str],
    ) -> dict[str, Any]:
        return {
            "service_id": service_item.service_id,
            "service_name": service_names.get(service_item.service_id),
            "description": service_item.description,
            "value": service_item.value,
            "currency": service_item.currency.value if hasattr(service_item.currency, "value") else str(service_item.currency),
            "start_date": service_item.start_date.isoformat(),
            "end_date": service_item.end_date.isoformat(),
        }

    @classmethod
    def _serialize_contract(
        cls,
        document: DocumentTable,
        today: date,
        service_items: Sequence[DocumentServiceTable] | None = None,
        service_names: dict[int, str] | None = None,
    ) -> dict[str, Any]:
        form_data = document.form_data if isinstance(document.form_data, dict) else {}
        resolved_service_items = list(service_items or [])
        resolved_service_names = service_names or {}

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
            "is_currently_active": cls._is_currently_active(document=document, today=today),
            "service_items": [
                cls._serialize_service_item(service_item=item, service_names=resolved_service_names) for item in resolved_service_items
            ],
            "file_name": document.file_name,
        }

    async def _load_service_context(
        self,
        organization_id: int,
        documents: Sequence[DocumentTable],
    ) -> tuple[dict[int, Sequence[DocumentServiceTable]], dict[int, str]]:
        document_ids = [document.id for document in documents if document.id is not None]
        if not document_ids:
            return {}, {}

        service_items_by_document = await self.sql_repo.get_document_services_by_document_ids(document_ids=document_ids)
        service_ids = sorted({item.service_id for items in service_items_by_document.values() for item in items})
        if not service_ids:
            return service_items_by_document, {}

        services = await self.service_repo.get_services_by_ids(organization_id=organization_id, service_ids=service_ids)
        service_names = {service.id: service.name for service in services if service.id is not None}
        return service_items_by_document, service_names

    async def run_query(self, organization_id: int, query: ContractQueryDTO) -> dict[str, Any]:
        """Ejecuta una consulta estructurada sobre los contratos de la organización con los filtros y operación especificados."""
        today = date.today()

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
            "evaluated_on": today.isoformat(),
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
                "currently_active": query.currently_active,
                "sort_by": query.sort_by,
                "sort_direction": query.sort_direction,
            },
        }

        if query.operation == "count":
            return response

        if query.operation == "ranking":
            items = await self.sql_repo.rank_contracts_by_client(
                organization_id=organization_id,
                query=query,
                limit=resolved_limit,
            )
            response["items"] = items
            response["returned_items"] = len(items)
            response["limit"] = resolved_limit
            return response

        documents = await self.sql_repo.search_contracts(organization_id=organization_id, query=query, limit=resolved_limit)
        service_items_by_document, service_names = await self._load_service_context(
            organization_id=organization_id,
            documents=documents,
        )
        response["items"] = [
            self._serialize_contract(
                document=document,
                today=today,
                service_items=service_items_by_document.get(document.id, []) if document.id is not None else [],
                service_names=service_names,
            )
            for document in documents
        ]
        response["returned_items"] = len(response["items"])
        response["limit"] = resolved_limit
        return response
