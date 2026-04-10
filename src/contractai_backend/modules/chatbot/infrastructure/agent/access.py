"""Role-aware access helpers for chatbot permissions and tools."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from ....documents.domain.access_policy import get_readable_document_types
from ....documents.domain.value_objs import DocumentType
from ....users.domain.value_objs import UserRole

ROLE_PERMISSION_DENIED_RESPONSE = "No tienes permisos para acceder a esa informacion."

COMPANY_KEYWORDS = (
    "empresa",
    "empresas",
    "cliente",
    "clientes",
    "proveedor",
    "proveedores",
    "corporativo",
    "corporativos",
    "comercial",
    "comerciales",
    "sociedad",
)

LABOR_KEYWORDS = (
    "trabajador",
    "trabajadores",
    "empleado",
    "empleados",
    "laboral",
    "laborales",
    "rrhh",
    "recursos humanos",
    "personal",
    "planilla",
    "practicante",
    "practicantes",
    "colaborador",
    "colaboradores",
)


@dataclass(frozen=True)
class DocumentAccessDecision:
    allowed_document_types: frozenset[DocumentType] | None
    requested_document_types: frozenset[DocumentType]
    denied_document_types: frozenset[DocumentType]

    @property
    def is_denied(self) -> bool:
        return bool(self.denied_document_types)

    def to_prompt_payload(self) -> dict[str, object]:
        return {
            "allowed_document_types": None
            if self.allowed_document_types is None
            else [document_type.value for document_type in sorted(self.allowed_document_types, key=lambda value: value.value)],
            "requested_document_types": [
                document_type.value for document_type in sorted(self.requested_document_types, key=lambda value: value.value)
            ],
            "denied_document_types": [document_type.value for document_type in sorted(self.denied_document_types, key=lambda value: value.value)],
            "must_deny": self.is_denied,
        }


def normalize_access_text(value: str) -> str:
    """Normalize user text for lightweight access inference."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(normalized.lower().strip().split())


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
    """Infer document-type intent from user or tool queries."""
    normalized = normalize_access_text(message)
    requested_types: set[DocumentType] = set()

    if any(keyword in normalized for keyword in COMPANY_KEYWORDS):
        requested_types.add(DocumentType.COMPANY)

    if any(keyword in normalized for keyword in LABOR_KEYWORDS):
        requested_types.add(DocumentType.LABOR)

    return frozenset(requested_types)


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
