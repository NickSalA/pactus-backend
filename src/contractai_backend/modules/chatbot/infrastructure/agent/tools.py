"""Tools personalizados para el agente de chatbot, integrando la búsqueda en la base de conocimientos contractual."""

import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from langchain_core.tools import tool
from pydantic import ValidationError

from .....core.application.validation import format_pydantic_validation_error
from ....dashboard.application.services import DashboardService
from ....dashboard.domain.access_policy import ALLOWED_DASHBOARD_TYPES_BY_ROLE
from ....documents.application.dto import CompanyContractQueryDTO, LaborContractQueryDTO
from ....documents.application.services import ContractQueryService
from ....documents.domain.value_objs import CurrencyType, DocumentState, DocumentType
from ....users.domain.entities import UserTable
from ....users.domain.value_objs import UserRole
from ...application.repositories import VectorRepository
from .access import ROLE_PERMISSION_DENIED_RESPONSE, evaluate_document_access
from .chart_handlers import handle_loyalty, handle_origin, handle_retention, handle_top_companies, handle_top_services
from .patterns import resolve_requested_document_state


class CounterpartyLookupRepository(Protocol):
    async def search_contract_access_candidates(
        self,
        organization_id: int,
        query: str,
        limit: int = 10,
        chatbot_ready_only: bool = False,
        state: str | None = None,
    ) -> Sequence[dict[str, Any]]: ...


def _resolve_scoped_document_ids(document_ids: list[int] | None, allowed_document_ids: frozenset[int] | None) -> list[int] | None:
    if allowed_document_ids is None:
        return document_ids

    if not allowed_document_ids:
        return []

    if document_ids is None:
        return sorted(allowed_document_ids)

    return [document_id for document_id in document_ids if document_id in allowed_document_ids]


def build_bc_tool(
    repo: VectorRepository,
    user_role: UserRole | None,
    allowed_document_ids: Iterable[int] | None = None,
    document_ids_by_state: Mapping[DocumentState, Iterable[int]] | None = None,
):
    """Construye una herramienta para el agente, que utiliza el repositorio vectorial para buscar información en la base de conocimientos."""
    scoped_document_ids = None if allowed_document_ids is None else frozenset(allowed_document_ids)
    scoped_document_ids_by_state = {document_state: frozenset(document_ids) for document_state, document_ids in (document_ids_by_state or {}).items()}

    @tool(
        name_or_callable="bc_tool",
        description=(
            "Usala obligatoriamente para buscar informacion en contratos corporativos, "
            "anexos, acuerdos comerciales, SLAs y documentos legales. Devuelve fragmentos "
            "relevantes de la base de conocimientos contractual de la empresa. Tambien sirve "
            "para extraer datos textuales como firmantes, representantes, apoderados, clausulas y obligaciones. "
            "Si ya identificaste un contrato, pasa document_ids para restringir la busqueda a ese contrato."
        ),
    )
    async def bc_tool(query: str, limit: int = 5, document_ids: list[int] | None = None) -> str:
        access_decision = evaluate_document_access(message=query, user_role=user_role)
        if access_decision.is_denied:
            return ROLE_PERMISSION_DENIED_RESPONSE

        requested_state = resolve_requested_document_state(query)
        applicable_document_ids = (
            scoped_document_ids_by_state.get(requested_state, frozenset()) if requested_state is not None else scoped_document_ids
        )

        if applicable_document_ids is not None and not applicable_document_ids:
            return ""

        filtered_document_ids = _resolve_scoped_document_ids(document_ids=document_ids, allowed_document_ids=applicable_document_ids)
        if document_ids is not None and filtered_document_ids == []:
            return ROLE_PERMISSION_DENIED_RESPONSE

        return await repo.search_documents(query=query, limit=limit, document_ids=filtered_document_ids)

    return bc_tool


def build_party_lookup_tool(repo: CounterpartyLookupRepository, organization_id: int):
    """Builds a permission helper tool that resolves real contracts for one named party."""

    @tool(
        name_or_callable="party_lookup_tool",
        description=(
            "Usala en el agente de permisos cuando el usuario pregunte por un contrato con una persona o empresa especifica y el tipo de documento no sea explicito. "
            "Busca contratos reales por contraparte en la organizacion y devuelve document_id, nombre, client y document_type para decidir acceso. "
            "No responde contenido contractual; solo resuelve contratos candidatos para COMPANY o LABOR."
        ),
    )
    async def party_lookup_tool(party_name: str, limit: int = 5, state: DocumentState | None = None) -> str:
        normalized_party_name = " ".join(party_name.strip().split())
        if not normalized_party_name:
            return json.dumps(
                {
                    "status": "invalid_request",
                    "message": "party_name no puede estar vacio.",
                },
                ensure_ascii=True,
            )

        resolved_state = state or DocumentState.ACTIVE
        matches = list(
            await repo.search_contract_access_candidates(
                organization_id=organization_id,
                query=normalized_party_name,
                limit=limit,
                chatbot_ready_only=True,
                state=resolved_state,
            )
        )
        matched_document_types = sorted({document_type for item in matches if (document_type := item.get("document_type")) is not None})
        result = {
            "status": "success" if matches else "no_match",
            "query": normalized_party_name,
            "matches": matches,
            "matched_document_types": matched_document_types,
            "match_count": len(matches),
        }
        return json.dumps(result, ensure_ascii=True)

    return party_lookup_tool


def build_company_contracts_query_tool(service: ContractQueryService, organization_id: int):
    """Construye una herramienta para consultas estructuradas de contratos COMPANY."""

    @tool(
        name_or_callable="company_contracts_query_tool",
        description=(
            "Usala para contar, listar, ordenar y rankear contratos COMPANY. "
            " operation='count': cuenta contratos COMPANY. "
            " operation='list': lista y ordena contratos COMPANY por cliente, nombre, valor, moneda, estado, servicios, fechas. "
            " operation='ranking': ranking de clientes por cantidad de contratos COMPANY. "
            " operation='services_ranking': ranking de servicios por monto total contratado (suma de valores en cada moneda). "
            " operation='client_services_ranking': ranking de clientes por cantidad de servicios contratados. "
            " Filtros: client, ruc, contract_name, service_name, service_id, min_value, max_value, currency, state, period_start, period_end, date_mode, currently_active, sort_by, sort_direction, limit. "
            " Si el usuario pide montos sin moneda, pedira aclaracion. "
            " No es para extraer firmantes u otros datos textuales internos del contrato."
        ),
    )
    async def company_contracts_query_tool(
        operation: str,
        client: str | None = None,
        ruc: str | None = None,
        contract_name: str | None = None,
        service_name: str | None = None,
        service_id: int | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        currency: CurrencyType | None = None,
        state: DocumentState | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        date_mode: str = "overlap",
        currently_active: bool | None = None,
        sort_by: str | None = None,
        sort_direction: str = "asc",
        limit: int = 20,
    ) -> str:
        try:
            query = CompanyContractQueryDTO(
                operation=operation,
                client=client,
                ruc=ruc,
                contract_name=contract_name,
                service_name=service_name,
                service_id=service_id,
                min_value=min_value,
                max_value=max_value,
                currency=currency,
                state=state,
                period_start=period_start,
                period_end=period_end,
                date_mode=date_mode,
                currently_active=currently_active,
                sort_by=sort_by,
                sort_direction=sort_direction,
                limit=limit,
            )
        except ValidationError as exc:
            result = {
                "status": "invalid_request",
                "message": f"No se pudo interpretar uno de los filtros proporcionados: {format_pydantic_validation_error(exc)}",
            }
            return json.dumps(result, ensure_ascii=True)

        result = await service.run_company_query(organization_id=organization_id, query=query)
        return json.dumps(result, ensure_ascii=True)

    return company_contracts_query_tool


def build_labor_contracts_query_tool(service: ContractQueryService, organization_id: int):
    """Construye una herramienta para consultas estructuradas de contratos LABOR."""

    @tool(
        name_or_callable="labor_contracts_query_tool",
        description=(
            "Usala para contar y listar contratos LABOR. "
            " operation='count': cuenta contratos LABOR. "
            " operation='list': lista y ordena contratos LABOR por trabajador, posicion, nombre, modalidad, periodicidad, monto, moneda, estado, fechas. "
            " operation='ranking': NO DISPONIBLE para contratos LABOR (un trabajador no puede tener múltiples contratos activos). "
            " Filtros: worker_name, worker_document_number, position, contract_name, contract_modality, salary_periodicity, min_value, max_value, currency, state, period_start, period_end, date_mode, currently_active, sort_by, sort_direction, limit. "
            " Si el usuario pide montos sin moneda, pedira aclaracion. "
            " No es para extraer firmantes u otros datos textuales internos del contrato."
        ),
    )
    async def labor_contracts_query_tool(
        operation: str,
        worker_name: str | None = None,
        worker_document_number: str | None = None,
        position: str | None = None,
        contract_name: str | None = None,
        contract_modality: str | None = None,
        salary_periodicity: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        currency: CurrencyType | None = None,
        state: DocumentState | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        date_mode: str = "overlap",
        currently_active: bool | None = None,
        sort_by: str | None = None,
        sort_direction: str = "asc",
        limit: int = 20,
    ) -> str:
        try:
            query = LaborContractQueryDTO(
                operation=operation,
                worker_name=worker_name,
                worker_document_number=worker_document_number,
                position=position,
                contract_name=contract_name,
                contract_modality=contract_modality,
                salary_periodicity=salary_periodicity,
                min_value=min_value,
                max_value=max_value,
                currency=currency,
                state=state,
                period_start=period_start,
                period_end=period_end,
                date_mode=date_mode,
                currently_active=currently_active,
                sort_by=sort_by,
                sort_direction=sort_direction,
                limit=limit,
            )
        except ValidationError as exc:
            result = {
                "status": "invalid_request",
                "message": f"No se pudo interpretar uno de los filtros proporcionados: {format_pydantic_validation_error(exc)}",
            }
            return json.dumps(result, ensure_ascii=True)

        result = await service.run_labor_query(organization_id=organization_id, query=query)
        return json.dumps(result, ensure_ascii=True)

    return labor_contracts_query_tool


def build_dashboard_chart_tool(
    service: DashboardService,
    user: UserTable,
):
    """Builds a tool that queries dashboard analytics and returns structured ChartData."""
    allowed_types = ALLOWED_DASHBOARD_TYPES_BY_ROLE.get(user.role, frozenset())

    ops_text = ""
    if DocumentType.COMPANY in allowed_types:
        ops_text += " - 'top_services': Ranking de los servicios mas contratados por monto total.\n"
        ops_text += " - 'top_companies': Ranking de los clientes (empresas) con mayor volumen de contratos.\n"
        ops_text += " - 'loyalty': Tendencia mensual de renovacion de contratos B2B (fidelidad de empresas).\n"

    if DocumentType.LABOR in allowed_types:
        ops_text += " - 'retention': Tendencia mensual de renovacion de contratos laborales (retencion de trabajadores).\n"
        ops_text += " - 'origin': Distribucion de contratos laborales por origen o tipo de creacion.\n"

    if not ops_text:
        ops_text = " - No hay operaciones disponibles para tu rol."

    dynamic_description = (
        "Usala proactivamente cuando el usuario pida ver graficas, charts, dashboards, visualizaciones, "
        "tops, rankings, o estadisticas generales (ej: los X mas vendidos/rentables, retencion, fidelidad). "
        "Operaciones disponibles permitidas para este usuario:\n"
        f"{ops_text}"
        "Parametros opcionales: "
        " - currency: ('PEN' o 'USD'). Aplica solo para top_services y top_companies. "
        " - limit: entero para limitar los resultados (por defecto 5, max 20). Aplica solo para top_services y top_companies. "
        "Devuelve un JSON con type, layout, title, config y data listos para renderizar una grafica en el frontend."
    )

    @tool(
        name_or_callable="dashboard_chart_tool",
        description=dynamic_description,
    )
    async def dashboard_chart_tool(operation: str, currency: str | None = None, limit: int | None = None) -> str:
        if operation == "top_services":
            return await handle_top_services(service, user, currency, limit)
        elif operation == "top_companies":
            return await handle_top_companies(service, user, currency, limit)
        elif operation == "retention":
            return await handle_retention(service, user)
        elif operation == "loyalty":
            return await handle_loyalty(service, user)
        elif operation == "origin":
            return await handle_origin(service, user)

        return json.dumps(
            {"status": "invalid_request", "message": f"Operacion '{operation}' no reconocida. Operaciones validas: top_services."},
            ensure_ascii=True,
        )

    return dashboard_chart_tool
