"""Provides structured contract queries for analytics-style use cases."""

from collections.abc import Sequence
from datetime import date
from typing import Any

from ....users.domain.value_objs import UserRole
from ...domain import DocumentServiceTable, DocumentTable
from ...domain.access_policy import can_read_document_type, get_readable_document_types
from ...domain.value_objs import DocumentState, DocumentType
from ..dto import ContractQueryDTO
from ..repositories import DocumentQueryRepository
from ....catalog.application.repositories import ServiceRepository

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 50
ROLE_PERMISSION_DENIED_RESPONSE = "No tienes permisos para acceder a esa informacion."


class ContractQueryService:
    """Executes structured contract queries backed by the relational store."""

    def __init__(self, sql_repo: DocumentQueryRepository, service_repo: ServiceRepository | None = None):
        self.sql_repo = sql_repo
        self.service_repo = service_repo or sql_repo

    @staticmethod
    def _clamp_limit(limit: int | None) -> int:
        if limit is None:
            return DEFAULT_LIST_LIMIT
        return max(1, min(limit, MAX_LIST_LIMIT))

    @staticmethod
    def _is_currently_active(document: DocumentTable, today: date) -> bool:
        return document.start_date is not None and document.end_date is not None and document.start_date <= today <= document.end_date

    @staticmethod
    def _serialize_optional_date(value: date | None) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _scope_query_by_role(query: ContractQueryDTO, user_role: UserRole | None) -> ContractQueryDTO | None:
        readable_document_types = get_readable_document_types(user_role)
        if readable_document_types is None:
            return query

        if query.document_type is not None:
            resolved_document_type = DocumentType(query.document_type)
            if not can_read_document_type(user_role=user_role, document_type=resolved_document_type):
                return None
            return query

        if len(readable_document_types) == 1:
            return query.model_copy(update={"document_type": next(iter(readable_document_types))})

        return query

    @staticmethod
    def has_required_chatbot_contract_data(document: DocumentTable) -> bool:
        form_data = document.form_data if isinstance(document.form_data, dict) else {}
        return (
            document.name is not None
            and document.client is not None
            and document.type is not None
            and document.start_date is not None
            and document.end_date is not None
            and form_data.get("value") is not None
            and form_data.get("currency") is not None
        )

    @classmethod
    def is_chatbot_visible_contract(cls, document: DocumentTable) -> bool:
        return document.state == DocumentState.ACTIVE and cls.has_required_chatbot_contract_data(document=document)

    @staticmethod
    def _scope_query_for_chatbot(query: ContractQueryDTO) -> ContractQueryDTO:
        if query.state is not None:
            return query
        return query.model_copy(update={"state": DocumentState.ACTIVE})

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
            "type": document.type.value if document.type is not None and hasattr(document.type, "value") else document.type,
            "state": document.state.value if document.state is not None and hasattr(document.state, "value") else document.state,
            "start_date": cls._serialize_optional_date(document.start_date),
            "end_date": cls._serialize_optional_date(document.end_date),
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

    async def run_query(self, organization_id: int, query: ContractQueryDTO, user_role: UserRole | None = None) -> dict[str, Any]:
        """Ejecuta una consulta estructurada sobre los contratos de la organización con los filtros y operación especificados."""
        today = date.today()
        await self.sql_repo.sync_contract_states(organization_id=organization_id)

        scoped_query = self._scope_query_by_role(query=query, user_role=user_role)
        if scoped_query is None:
            return {"status": "forbidden", "message": ROLE_PERMISSION_DENIED_RESPONSE}
        scoped_query = self._scope_query_for_chatbot(query=scoped_query)

        base_query = self._scope_query_by_role(query=ContractQueryDTO(operation=query.operation, state=query.state), user_role=user_role)
        if base_query is None:
            return {"status": "forbidden", "message": ROLE_PERMISSION_DENIED_RESPONSE}
        base_query = self._scope_query_for_chatbot(query=base_query)

        if (scoped_query.min_value is not None or scoped_query.max_value is not None) and not scoped_query.currency:
            return {
                "status": "needs_clarification",
                "message": "Indique la moneda del monto a evaluar, por ejemplo USD, PEN o EUR.",
            }

        if scoped_query.period_start and scoped_query.period_end and scoped_query.period_start > scoped_query.period_end:
            return {
                "status": "invalid_request",
                "message": "La fecha inicial no puede ser posterior a la fecha final.",
            }

        resolved_limit = self._clamp_limit(scoped_query.limit)

        total_contracts = await self.sql_repo.count_contracts(
            organization_id=organization_id,
            query=base_query,
            chatbot_ready_only=True,
        )
        if total_contracts == 0:
            return {
                "status": "no_data",
                "message": "No hay contratos cargados para la organizacion actual.",
            }

        filtered_count = await self.sql_repo.count_contracts(
            organization_id=organization_id,
            query=scoped_query,
            chatbot_ready_only=True,
        )

        response: dict[str, Any] = {
            "status": "success",
            "operation": scoped_query.operation,
            "count": filtered_count,
            "total_contracts_available": total_contracts,
            "evaluated_on": today.isoformat(),
            "filters_applied": {
                "client": scoped_query.client,
                "contract_name": scoped_query.contract_name,
                "min_value": scoped_query.min_value,
                "max_value": scoped_query.max_value,
                "currency": scoped_query.currency,
                "state": scoped_query.state,
                "document_type": scoped_query.document_type,
                "period_start": scoped_query.period_start.isoformat() if scoped_query.period_start else None,
                "period_end": scoped_query.period_end.isoformat() if scoped_query.period_end else None,
                "date_mode": scoped_query.date_mode,
                "currently_active": scoped_query.currently_active,
                "sort_by": scoped_query.sort_by,
                "sort_direction": scoped_query.sort_direction,
            },
        }

        if scoped_query.operation == "count":
            return response

        if scoped_query.operation == "ranking":
            items = await self.sql_repo.rank_contracts_by_client(
                organization_id=organization_id,
                query=scoped_query,
                limit=resolved_limit,
                chatbot_ready_only=True,
            )
            response["items"] = items
            response["returned_items"] = len(items)
            response["limit"] = resolved_limit
            return response

        documents = await self.sql_repo.search_contracts(
            organization_id=organization_id,
            query=scoped_query,
            limit=resolved_limit,
            chatbot_ready_only=True,
        )
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
