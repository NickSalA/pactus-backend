"""Role-aware access helpers for chatbot permissions and tools."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ....documents.domain.access_policy import get_readable_document_types
from ....documents.domain.value_objs import DocumentType
from ....users.domain.value_objs import UserRole

ROLE_PERMISSION_DENIED_RESPONSE = "No tienes permisos para acceder a esa informacion."

EXPLICIT_DOCUMENT_TYPE_PATTERNS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.COMPANY: (
        r"\bempresa(?:s)?\b",
        r"\bcliente(?:s)?\b",
        r"\bproveedor(?:es)?\b",
        r"\bcorporativ(?:o|a|os|as)\b",
        r"\bcomercial(?:es)?\b",
    ),
    DocumentType.LABOR: (
        r"\blabor(?:al(?:es)?)?\b",
        r"\btrabajador(?:es)?\b",
        r"\bemplead(?:o|a|os|as)\b",
        r"\brrhh\b",
        r"\brecursos humanos\b",
        r"\bplanilla\b",
    ),
}

NAMED_PARTY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bcontratos?\s+(?:de|con)\s+(?P<party>[^?.!,;]+)"),
    re.compile(r"\b(?:puesto(?:\s+de\s+trabajo)?|cargo|rol|funcion)\s+de\s+(?P<party>[^?.!,;]+)"),
)
TRAILING_PARTY_PATTERN = re.compile(r"\b(?:por favor|gracias|porfa)\b.*$")


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
    """Infer explicit document-type intent from the latest message."""
    normalized = normalize_access_text(message)
    requested_types = {
        document_type
        for document_type, patterns in EXPLICIT_DOCUMENT_TYPE_PATTERNS.items()
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
        candidate = TRAILING_PARTY_PATTERN.sub("", candidate).strip()
        if candidate:
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
