"""Role-aware access helpers for chatbot permissions and tools."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.tools import BaseTool

from ....documents.domain.access_policy import get_readable_document_types
from ....documents.domain.value_objs import DocumentType
from ....users.domain.value_objs import UserRole
from ...application.dto import DocumentAccessDecision
from .patterns import (
    EXPLICIT_DOCUMENT_TYPE_PATTERNS,
    NAMED_PARTY_PATTERNS,
    TRAILING_PARTY_PATTERN,
    normalize_access_text,
    resolve_requested_document_state,
)

logger = logging.getLogger(__name__)

ROLE_PERMISSION_DENIED_RESPONSE = "No tienes permisos para acceder a esa informacion."


def coerce_user_role(user_role: UserRole | str | None) -> UserRole | None:
    """Coerce raw role values into the domain enum when possible."""
    if isinstance(user_role, UserRole):
        return user_role

    if isinstance(user_role, str) and user_role.strip():
        try:
            return UserRole(user_role.strip().upper())
        except ValueError:
            return None

    return None


def infer_requested_document_types(message: str) -> frozenset[DocumentType]:
    """Infer explicit document-type intent from the latest message."""
    normalized = normalize_access_text(message)
    requested_types = {
        DocumentType(dt_value)
        for dt_value, patterns in EXPLICIT_DOCUMENT_TYPE_PATTERNS.items()
        if any(re.search(pattern, normalized) for pattern in patterns)
    }
    return frozenset(requested_types)


def extract_contract_party_candidate(message: str) -> str | None:
    """Extract the named person/company from contract-related queries like 'contrato de X' or 'cargo de X'."""
    normalized = normalize_access_text(message)
    for pattern in NAMED_PARTY_PATTERNS:
        matches = list(pattern.finditer(normalized))
        if not matches:
            continue

        candidate = matches[-1].group("party").strip()
        if candidate := TRAILING_PARTY_PATTERN.sub("", candidate).strip():
            return candidate

    return None


def evaluate_document_access(message: str, user_role: UserRole | str | None) -> DocumentAccessDecision:
    """Evaluate whether the message explicitly targets forbidden document types for the role."""
    role = coerce_user_role(user_role)
    allowed_document_types = get_readable_document_types(role)
    requested_document_types = infer_requested_document_types(message)

    if allowed_document_types is None:
        denied_document_types = frozenset()
    else:
        denied_document_types = frozenset(document_type for document_type in requested_document_types if document_type not in allowed_document_types)

    return DocumentAccessDecision(
        allowed_document_types=allowed_document_types,
        requested_document_types=requested_document_types,
        denied_document_types=denied_document_types,
    )


def _get_permission_tool(tools: Sequence[BaseTool], tool_name: str) -> BaseTool | None:
    return next((tool for tool in tools if tool.name == tool_name), None)


def _get_allowed_document_types(user_context: Mapping[str, Any], access_decision: DocumentAccessDecision) -> set[str] | None:
    if access_decision.allowed_document_types is not None:
        return {document_type.value for document_type in access_decision.allowed_document_types}

    raw_allowed_document_types = user_context.get("allowed_document_types")
    if raw_allowed_document_types is None:
        return None

    return {str(document_type) for document_type in raw_allowed_document_types}


def _normalize_contract_candidates(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_matches: list[dict[str, Any]] = []
    seen_document_ids: set[int] = set()
    for match in matches:
        try:
            document_id = int(match["document_id"])
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Failed to parse document_id from match: %s. Error: %s", match, e)
            continue

        if document_id in seen_document_ids:
            continue

        document_type = match.get("document_type")
        if document_type is None:
            continue

        seen_document_ids.add(document_id)
        normalized_matches.append(
            {
                "document_id": document_id,
                "name": match.get("name"),
                "client": match.get("client"),
                "document_type": str(document_type),
                "file_name": match.get("file_name"),
                "match_score": float(match.get("match_score") or 0.0),
            }
        )

    normalized_matches.sort(key=lambda item: (item["match_score"], str(item.get("client") or "")), reverse=True)
    return normalized_matches


def _format_contract_candidate(candidate: dict[str, Any]) -> str:
    identifier = candidate.get("name") or candidate.get("file_name") or candidate.get("client") or f"Documento {candidate['document_id']}"
    return (
        f"{identifier} | Contraparte: {candidate.get('client') or 'Sin nombre'} | "
        f"Tipo: {candidate.get('document_type')} | Documento: {candidate['document_id']}"
    )


def _build_permission_clarification_response(party_candidate: str, allowed_matches: list[dict[str, Any]]) -> str:
    options = "\n".join(f"{index}. {_format_contract_candidate(candidate)}" for index, candidate in enumerate(allowed_matches[:3], start=1))
    return f"Encontre varios contratos a los que si tienes acceso relacionados con '{party_candidate}'. Indica cual necesitas:\n{options}"


async def _invoke_party_lookup_tool(
    message: str,
    tools: Sequence[BaseTool],
    party_candidate: str,
) -> list[dict[str, Any]] | None:
    """Call the party lookup tool and return the raw matches list if available."""
    party_lookup_tool = _get_permission_tool(tools, "party_lookup_tool")
    if party_lookup_tool is None:
        return None

    tool_payload: dict[str, Any] = {"party_name": party_candidate, "limit": 10}
    requested_state = resolve_requested_document_state(message)
    if requested_state is not None:
        tool_payload["state"] = requested_state

    raw_result = await party_lookup_tool.ainvoke(tool_payload)
    try:
        lookup_result = json.loads(str(raw_result))
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON result from party_lookup_tool: %s", raw_result)
        return None

    matches = lookup_result.get("matches")
    return matches if isinstance(matches, list) else None


def _partition_matches_by_permission(
    normalized_matches: list[dict[str, Any]],
    user_context: Mapping[str, Any],
    access_decision: DocumentAccessDecision,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split matches into allowed and denied according to the access decision."""
    allowed_document_types = _get_allowed_document_types(
        user_context=user_context,
        access_decision=access_decision,
    )
    if allowed_document_types is None:
        return normalized_matches, []

    allowed_matches = [match for match in normalized_matches if match["document_type"] in allowed_document_types]
    denied_matches = [match for match in normalized_matches if match["document_type"] not in allowed_document_types]
    return allowed_matches, denied_matches


def _build_access_resolution_response(
    party_candidate: str,
    allowed_matches: list[dict[str, Any]],
    denied_matches: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the final resolution response based on allowed/denied matches."""
    if not allowed_matches:
        return {"kind": "deny"} if denied_matches else {"kind": "no_match"}

    if len(allowed_matches) == 1:
        return {
            "kind": "allow",
            "document_ids": [allowed_matches[0]["document_id"]],
            "candidates": allowed_matches,
        }

    return {
        "kind": "clarify",
        "response": _build_permission_clarification_response(
            party_candidate=party_candidate,
            allowed_matches=allowed_matches,
        ),
        "candidates": allowed_matches,
    }


async def resolve_named_party_access(
    message: str,
    user_context: Mapping[str, Any],
    access_decision: DocumentAccessDecision,
    tools: Sequence[BaseTool],
) -> dict[str, Any] | None:
    party_candidate = extract_contract_party_candidate(message)
    if party_candidate is None:
        return None

    matches = await _invoke_party_lookup_tool(
        message=message,
        tools=tools,
        party_candidate=party_candidate,
    )
    if matches is None:
        return None

    normalized_matches = _normalize_contract_candidates(matches)
    if not normalized_matches:
        return {"kind": "no_match"}

    allowed_matches, denied_matches = _partition_matches_by_permission(
        normalized_matches=normalized_matches,
        user_context=user_context,
        access_decision=access_decision,
    )

    return _build_access_resolution_response(
        party_candidate=party_candidate,
        allowed_matches=allowed_matches,
        denied_matches=denied_matches,
    )
