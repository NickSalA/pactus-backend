"""Provides structured contract queries for analytics-style use cases."""

from collections.abc import Sequence
from datetime import date
from typing import Any, cast

from ....catalog.application.repositories import ServiceRepository
from ....users.domain.value_objs import UserRole
from ...domain import CompanyContractServiceTable, DocumentTable
from ...domain.access_policy import can_read_document_type, get_readable_document_types
from ...domain.value_objs import DocumentState, DocumentType
from ..dto import ContractQueryDTO
from ..repositories import DocumentQueryRepository

DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 50
ROLE_PERMISSION_DENIED_RESPONSE = "No tienes permisos para acceder a esa informacion."


class ContractQueryService:
    """Executes structured contract queries backed by the relational store."""

    def __init__(self, sql_repo: DocumentQueryRepository, service_repo: ServiceRepository | None = None):
        self.sql_repo = sql_repo
        self.service_repo = service_repo or cast(ServiceRepository, sql_repo)

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
    def _is_document_with_child(document: DocumentTable) -> bool:
        return document.type is not None

    @classmethod
    def is_chatbot_visible_contract(cls, document: DocumentTable) -> bool:
        if document.state not in (DocumentState.ACTIVE, DocumentState.EXPIRING_SOON):
            return False
        return cls._is_document_with_child(document)

    @staticmethod
    def _scope_query_for_chatbot(query: ContractQueryDTO) -> ContractQueryDTO:
        if query.state is not None:
            return query
        return query.model_copy(update={"state": DocumentState.ACTIVE})

    @staticmethod
    def _serialize_service_item(
        service_item: CompanyContractServiceTable,
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
        service_items: Sequence[CompanyContractServiceTable] | None = None,
        service_names: dict[int, str] | None = None,
        client: str | None = None,
        labor_value: float | None = None,
        labor_currency: str | None = None,
        company_total_value: float | None = None,
        company_currency: str | None = None,
    ) -> dict[str, Any]:
        form_data = document.form_data if isinstance(document.form_data, dict) else {}
        resolved_service_items = list(service_items or [])
        resolved_service_names = service_names or {}

        is_company = document.type == DocumentType.COMPANY if document.type else False
        contract_value = company_total_value if is_company else labor_value
        contract_currency = company_currency if is_company else labor_currency

        return {
            "id": document.id,
            "name": document.file_name,
            "client": client,
            "type": document.type.value if document.type is not None and hasattr(document.type, "value") else document.type,
            "state": document.state.value if document.state is not None and hasattr(document.state, "value") else document.state,
            "start_date": cls._serialize_optional_date(document.start_date),
            "end_date": cls._serialize_optional_date(document.end_date),
            "value": contract_value,
            "currency": contract_currency,
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
    ) -> tuple[dict[int, Sequence[CompanyContractServiceTable]], dict[int, str]]:
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

    async def _run_services_ranking(self, organization_id: int, query: ContractQueryDTO, user_role: UserRole | None = None) -> dict[str, Any]:
        document_ids = await self.sql_repo.get_all_document_ids_with_chatbot_ready(
            organization_id=organization_id,
        )
        if not document_ids:
            return {"status": "no_data", "message": "No hay datos disponibles.", "items": [], "returned_items": 0}

        service_items_by_document = await self.sql_repo.get_document_services_by_document_ids(document_ids=document_ids)

        service_ids = sorted({item.service_id for items in service_items_by_document.values() for item in items})
        service_names: dict[int, str] = {}
        if service_ids:
            services = await self.sql_repo.get_services_by_ids(organization_id=organization_id, service_ids=service_ids)
            service_names = {service.id: service.name for service in services if service.id is not None}

        service_totals: dict[int, dict[str, Any]] = {}
        for doc_id, items in service_items_by_document.items():
            for item in items:
                if item.service_id not in service_totals:
                    service_totals[item.service_id] = {
                        "service_id": item.service_id,
                        "service_name": service_names.get(item.service_id, f"Servicio {item.service_id}"),
                        "contracts_count": 0,
                        "total_quantity": 0.0,
                    }
                service_totals[item.service_id]["contracts_count"] += 1
                service_totals[item.service_id]["total_quantity"] += float(item.quantity or 0)

        sorted_services = sorted(
            service_totals.values(),
            key=lambda x: x["total_quantity"],
            reverse=True,
        )

        return {
            "status": "success",
            "message": "Ranking de servicios por cantidad total contratada.",
            "items": sorted_services,
            "returned_items": len(sorted_services),
        }

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

        if scoped_query.operation == "services_ranking":
            return await self._run_services_ranking(organization_id=organization_id, query=scoped_query, user_role=user_role)

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
                "service_name": scoped_query.service_name,
                "service_id": scoped_query.service_id,
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

        if scoped_query.operation == "services_ranking":
            return await self._run_services_ranking(organization_id=organization_id, query=scoped_query, user_role=user_role)

        documents = await self.sql_repo.search_contracts(
            organization_id=organization_id,
            query=scoped_query,
            limit=resolved_limit,
            chatbot_ready_only=True,
        )
        document_ids = [doc.id for doc in documents if doc.id is not None]
        value_context = await self.sql_repo.get_contract_value_context(document_ids=document_ids) if document_ids else {}
        party_context = await self.sql_repo.get_contract_party_context(document_ids=document_ids) if document_ids else {}
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
                client=party_context.get(document.id) if document.id else None,
                labor_value=value_context.get(document.id, {}).get("labor_value") if document.id else None,
                labor_currency=value_context.get(document.id, {}).get("labor_currency") if document.id else None,
                company_total_value=value_context.get(document.id, {}).get("company_total_value") if document.id else None,
                company_currency=value_context.get(document.id, {}).get("company_currency") if document.id else None,
            )
            for document in documents
        ]
        response["returned_items"] = len(response["items"])
        response["limit"] = resolved_limit
        return response
