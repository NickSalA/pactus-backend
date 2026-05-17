"""Tools personalizados para el agente de chatbot, integrando la búsqueda en la base de conocimientos contractual."""

import json
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from langchain_core.tools import tool
from pydantic import ValidationError

from .....core.application.validation import format_pydantic_validation_error
from ....documents.application.dto import ContractQueryDTO
from ....documents.application.services import ContractQueryService
from ....documents.domain.value_objs import CurrencyType, DocumentState, DocumentType
from ....users.domain.value_objs import UserRole
from ...application.repositories import VectorRepository
from .access import ROLE_PERMISSION_DENIED_RESPONSE, evaluate_document_access


class CounterpartyLookupRepository(Protocol):
    async def search_contract_access_candidates(
        self,
        organization_id: int,
        query: str,
        limit: int = 10,
        chatbot_ready_only: bool = False,
        state: str | None = None,
    ) -> Sequence[dict[str, Any]]: ...


STATE_PATTERNS: tuple[tuple[DocumentState, tuple[str, ...]], ...] = (
    (DocumentState.PENDING_SIGNATURE, (r"\bpendiente(?:s)? de firma\b", r"\bpor firmar\b", r"\bpending signature\b")),
    (DocumentState.EXPIRING_SOON, (r"\bpor vencer\b", r"\bpor vencerse\b", r"\bexpira(?:n)? pronto\b", r"\bexpiring soon\b")),
    (DocumentState.EXPIRED, (r"\bvencid(?:o|a|os|as)\b", r"\bexpirad(?:o|a|os|as)\b", r"\bexpired\b")),
    (DocumentState.TERMINATED, (r"\bterminad(?:o|a|os|as)\b", r"\bresuelt(?:o|a|os|as)\b", r"\bterminated\b")),
    (DocumentState.DRAFT, (r"\bborrador(?:es)?\b", r"\bdrafts?\b")),
    (DocumentState.ACTIVE, (r"\bactive\b", r"\bactiv(?:o|a|os|as)\b", r"\bvigente(?:s)?\b")),
)


def resolve_requested_document_state(message: str) -> DocumentState | None:
    normalized = unicodedata.normalize("NFKD", message or "").encode("ascii", "ignore").decode("ascii").lower()
    for document_state, patterns in STATE_PATTERNS:
        if any(re.search(pattern, normalized) for pattern in patterns):
            return document_state
    return None


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


def build_contracts_query_tool(service: ContractQueryService, organization_id: int, user_role: UserRole | None):
    """Construye una herramienta para consultas estructuradas de contratos."""

    @tool(
        name_or_callable="contracts_query_tool",
        description=(
            "Usala para contar, listar, ordenar y rankear contratos como registros por cliente, nombre, valor total, moneda, "
            "estado, tipo, servicios asociados y rangos de fechas. Tambien sirve para identificar contratos vigentes hoy, "
            "filtrar por service_id o service_name y devolver sus servicios asociados. "
            "No es para extraer nombres de firmantes u otros datos textuales internos del contrato. Si el usuario pide montos sin moneda, "
            "esta herramienta indicara que se debe pedir aclaracion."
        ),
    )
    async def contracts_query_tool(
        operation: str,
        client: str | None = None,
        contract_name: str | None = None,
        service_name: str | None = None,
        service_id: int | None = None,
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
                service_name=service_name,
                service_id=service_id,
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

        result = await service.run_query(organization_id=organization_id, query=query, user_role=user_role)
        return json.dumps(result, ensure_ascii=True)

    return contracts_query_tool
