"""Provides structured contract queries for analytics-style use cases."""

from collections.abc import Sequence
from datetime import date
from typing import Any, cast

from ....catalog.application.repositories import ServiceRepository
from ...domain import CompanyContractServiceTable, DocumentTable
from ..dto import CompanyContractQueryDTO, LaborContractQueryDTO
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
    def is_chatbot_visible_contract(document: DocumentTable) -> bool:
        if document.start_date is None or document.end_date is None:
            return False
        if document.type is None:
            return False
        return True

    @staticmethod
    def _serialize_optional_date(value: date | None) -> str | None:
        return value.isoformat() if value is not None else None

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
    def _serialize_company_contract(
        cls,
        document: DocumentTable,
        today: date,
        service_items: Sequence[CompanyContractServiceTable] | None = None,
        service_names: dict[int, str] | None = None,
        client: str | None = None,
        company_total_value: float | None = None,
        company_currency: str | None = None,
    ) -> dict[str, Any]:
        resolved_service_items = list(service_items or [])
        resolved_service_names = service_names or {}

        return {
            "id": document.id,
            "name": document.file_name,
            "client": client,
            "type": document.type.value if document.type is not None and hasattr(document.type, "value") else document.type,
            "state": document.state.value if document.state is not None and hasattr(document.state, "value") else document.state,
            "start_date": cls._serialize_optional_date(document.start_date),
            "end_date": cls._serialize_optional_date(document.end_date),
            "value": company_total_value,
            "currency": company_currency,
            "is_currently_active": cls._is_currently_active(document=document, today=today),
            "service_items": [
                cls._serialize_service_item(service_item=item, service_names=resolved_service_names) for item in resolved_service_items
            ],
            "file_name": document.file_name,
        }

    @classmethod
    def _serialize_labor_contract(
        cls,
        document: DocumentTable,
        today: date,
        worker_name: str | None = None,
        worker_document_number: str | None = None,
        position: str | None = None,
        labor_value: float | None = None,
        labor_currency: str | None = None,
    ) -> dict[str, Any]:
        return {
            "id": document.id,
            "name": document.file_name,
            "worker_name": worker_name,
            "worker_document_number": worker_document_number,
            "position": position,
            "type": document.type.value if document.type is not None and hasattr(document.type, "value") else document.type,
            "state": document.state.value if document.state is not None and hasattr(document.state, "value") else document.state,
            "start_date": cls._serialize_optional_date(document.start_date),
            "end_date": cls._serialize_optional_date(document.end_date),
            "value": labor_value,
            "currency": labor_currency,
            "is_currently_active": cls._is_currently_active(document=document, today=today),
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

    async def _run_company_services_ranking(self, organization_id: int) -> dict[str, Any]:
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

        service_totals: dict[tuple[int, str], dict[str, Any]] = {}
        for doc_id, items in service_items_by_document.items():
            for item in items:
                key = (item.service_id, item.currency.value if hasattr(item.currency, 'value') else str(item.currency))
                if key not in service_totals:
                    service_totals[key] = {
                        "service_id": item.service_id,
                        "service_name": service_names.get(item.service_id, f"Servicio {item.service_id}"),
                        "currency": item.currency.value if hasattr(item.currency, 'value') else str(item.currency),
                        "contracts_count": 0,
                        "total_value": 0.0,
                    }
                service_totals[key]["contracts_count"] += 1
                service_totals[key]["total_value"] += float(item.value or 0)

        sorted_services = sorted(
            service_totals.values(),
            key=lambda x: x["total_value"],
            reverse=True,
        )

        return {
            "status": "success",
            "message": "Ranking de servicios por monto total contratado.",
            "items": sorted_services,
            "returned_items": len(sorted_services),
        }

    async def _run_company_client_services_ranking(self, organization_id: int, query: CompanyContractQueryDTO) -> dict[str, Any]:
        resolved_limit = self._clamp_limit(query.limit)

        items = await self.sql_repo.rank_company_contracts_by_services(
            organization_id=organization_id,
            query=query,
            limit=resolved_limit,
            chatbot_ready_only=True,
        )

        return {
            "status": "success",
            "message": "Ranking de clientes por cantidad de servicios contratados.",
            "items": items,
            "returned_items": len(items),
            "limit": resolved_limit,
        }

    async def run_company_query(self, organization_id: int, query: CompanyContractQueryDTO) -> dict[str, Any]:
        """Ejecuta una consulta estructurada sobre contratos COMPANY."""
        today = date.today()
        await self.sql_repo.sync_contract_states(organization_id=organization_id)

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

        if query.operation == "services_ranking":
            return await self._run_company_services_ranking(organization_id=organization_id)

        if query.operation == "client_services_ranking":
            return await self._run_company_client_services_ranking(organization_id=organization_id, query=query)

        resolved_limit = self._clamp_limit(query.limit)

        total_contracts = await self.sql_repo.count_company_contracts(
            organization_id=organization_id,
            query=query,
            chatbot_ready_only=True,
        )
        if total_contracts == 0:
            return {
                "status": "no_data",
                "message": "No hay contratos COMPANY cargados para la organizacion actual.",
            }

        filtered_count = await self.sql_repo.count_company_contracts(
            organization_id=organization_id,
            query=query,
            chatbot_ready_only=True,
        )

        response: dict[str, Any] = {
            "status": "success",
            "operation": query.operation,
            "document_type": "COMPANY",
            "count": filtered_count,
            "total_contracts_available": total_contracts,
            "evaluated_on": today.isoformat(),
            "filters_applied": {
                "client": query.client,
                "ruc": query.ruc,
                "contract_name": query.contract_name,
                "service_name": query.service_name,
                "service_id": query.service_id,
                "min_value": query.min_value,
                "max_value": query.max_value,
                "currency": query.currency,
                "state": query.state,
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
            items = await self.sql_repo.rank_company_contracts_by_client(
                organization_id=organization_id,
                query=query,
                limit=resolved_limit,
                chatbot_ready_only=True,
            )
            response["items"] = items
            response["returned_items"] = len(items)
            response["limit"] = resolved_limit
            return response

        documents = await self.sql_repo.search_company_contracts(
            organization_id=organization_id,
            query=query,
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
            self._serialize_company_contract(
                document=document,
                today=today,
                service_items=service_items_by_document.get(document.id, []) if document.id is not None else [],
                service_names=service_names,
                client=party_context.get(document.id) if document.id else None,
                company_total_value=value_context.get(document.id, {}).get("company_total_value") if document.id else None,
                company_currency=value_context.get(document.id, {}).get("company_currency") if document.id else None,
            )
            for document in documents
        ]
        response["returned_items"] = len(response["items"])
        response["limit"] = resolved_limit
        return response

    async def run_labor_query(self, organization_id: int, query: LaborContractQueryDTO) -> dict[str, Any]:
        """Ejecuta una consulta estructurada sobre contratos LABOR."""
        today = date.today()
        await self.sql_repo.sync_contract_states(organization_id=organization_id)

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

        total_contracts = await self.sql_repo.count_labor_contracts(
            organization_id=organization_id,
            query=query,
            chatbot_ready_only=True,
        )
        if total_contracts == 0:
            return {
                "status": "no_data",
                "message": "No hay contratos LABOR cargados para la organizacion actual.",
            }

        filtered_count = await self.sql_repo.count_labor_contracts(
            organization_id=organization_id,
            query=query,
            chatbot_ready_only=True,
        )

        response: dict[str, Any] = {
            "status": "success",
            "operation": query.operation,
            "document_type": "LABOR",
            "count": filtered_count,
            "total_contracts_available": total_contracts,
            "evaluated_on": today.isoformat(),
            "filters_applied": {
                "worker_name": query.worker_name,
                "worker_document_number": query.worker_document_number,
                "position": query.position,
                "contract_name": query.contract_name,
                "contract_modality": query.contract_modality,
                "salary_periodicity": query.salary_periodicity,
                "min_value": query.min_value,
                "max_value": query.max_value,
                "currency": query.currency,
                "state": query.state,
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

        documents = await self.sql_repo.search_labor_contracts(
            organization_id=organization_id,
            query=query,
            limit=resolved_limit,
            chatbot_ready_only=True,
        )
        document_ids = [doc.id for doc in documents if doc.id is not None]
        value_context = await self.sql_repo.get_contract_value_context(document_ids=document_ids) if document_ids else {}
        party_context = await self.sql_repo.get_contract_party_context(document_ids=document_ids) if document_ids else {}

        labor_details = await self._get_labor_contract_details(document_ids) if document_ids else {}

        response["items"] = [
            self._serialize_labor_contract(
                document=document,
                today=today,
                worker_name=party_context.get(document.id) if document.id else None,
                worker_document_number=labor_details.get(document.id, {}).get("worker_document_number") if document.id else None,
                position=labor_details.get(document.id, {}).get("position") if document.id else None,
                labor_value=value_context.get(document.id, {}).get("labor_value") if document.id else None,
                labor_currency=value_context.get(document.id, {}).get("labor_currency") if document.id else None,
            )
            for document in documents
        ]
        response["returned_items"] = len(response["items"])
        response["limit"] = resolved_limit
        return response

    async def _get_labor_contract_details(self, document_ids: list[int]) -> dict[int, dict[str, Any]]:
        """Fetch labor contract details for a list of document IDs."""
        details: dict[int, dict[str, Any]] = {}
        for doc_id in document_ids:
            labor_contract = await self.sql_repo.get_labor_contract_by_document_id(doc_id)
            if labor_contract:
                details[doc_id] = {
                    "worker_document_number": labor_contract.worker_document_number,
                    "position": labor_contract.position,
                }
        return details
