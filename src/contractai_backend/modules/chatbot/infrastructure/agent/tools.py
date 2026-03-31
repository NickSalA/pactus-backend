"""Tools personalizados para el agente de chatbot, integrando la búsqueda en la base de conocimientos contractual."""

import json
from datetime import datetime

from langchain_core.tools import tool
from pydantic import ValidationError

from .....core.application.validation import format_pydantic_validation_error
from ....documents.application.dto import ContractQueryDTO
from ....documents.application.services import ContractQueryService
from ....documents.domain.value_objs import CurrencyType, DocumentState, DocumentType
from ...application.repositories import VectorRepository


def build_bc_tool(repo: VectorRepository):
    """Construye una herramienta para el agente, que utiliza el repositorio vectorial para buscar información en la base de conocimientos."""

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
        return await repo.search_documents(query=query, limit=limit, document_ids=document_ids)

    return bc_tool


def build_contracts_query_tool(service: ContractQueryService, organization_id: int):
    """Construye una herramienta para consultas estructuradas de contratos."""

    @tool(
        name_or_callable="contracts_query_tool",
        description=(
            "Usala para contar, listar, ordenar y rankear contratos como registros por cliente, nombre, valor total, moneda, "
            "estado, tipo y rangos de fechas. Tambien sirve para identificar contratos vigentes hoy y devolver sus servicios asociados. "
            "No es para extraer nombres de firmantes u otros datos textuales internos del contrato. Si el usuario pide montos sin moneda, "
            "esta herramienta indicara que se debe pedir aclaracion."
        ),
    )
    async def contracts_query_tool(  # noqa: PLR0913
        operation: str,
        client: str | None = None,
        contract_name: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        currency: CurrencyType | None = None,
        state: DocumentState | None = None,
        document_type: DocumentType | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        date_mode: str = "overlap",
        currently_active: bool | None = None,
        sort_by: str | None = None,
        sort_direction: str = "asc",
        limit: int = 20,
    ) -> str:
        try:
            query = ContractQueryDTO(
                operation=operation,
                client=client,
                contract_name=contract_name,
                min_value=min_value,
                max_value=max_value,
                currency=currency,
                state=state,
                document_type=document_type,
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

        result = await service.run_query(organization_id=organization_id, query=query)
        return json.dumps(result, ensure_ascii=True)

    return contracts_query_tool
