"""Declarative patterns and text normalization utilities shared across the agent module."""

from __future__ import annotations

import re
import unicodedata

from ....documents.domain.value_objs import DocumentState


def normalize_access_text(value: str) -> str:
    """Normalize user text for lightweight access inference and pattern matching."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(normalized.lower().strip().split())


EXPLICIT_DOCUMENT_TYPE_PATTERNS: dict[str, tuple[str, ...]] = {
    "COMPANY": (
        r"\bempresa(?:s)?\b",
        r"\bcliente(?:s)?\b",
        r"\bproveedor(?:es)?\b",
        r"\bcorporativ(?:o|a|os|as)\b",
        r"\bcomercial(?:es)?\b",
    ),
    "LABOR": (
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


STATE_PATTERNS: tuple[tuple[DocumentState, tuple[str, ...]], ...] = (
    (
        DocumentState.PENDING_SIGNATURE,
        (r"\bpendiente(?:s)? de firma\b", r"\bpor firmar\b", r"\bpending signature\b"),
    ),
    (
        DocumentState.EXPIRING_SOON,
        (r"\bpor vencer\b", r"\bpor vencerse\b", r"\bexpira(?:n)? pronto\b", r"\bexpiring soon\b"),
    ),
    (
        DocumentState.EXPIRED,
        (r"\bvencid(?:o|a|os|as)\b", r"\bexpirad(?:o|a|os|as)\b", r"\bexpired\b"),
    ),
    (
        DocumentState.TERMINATED,
        (r"\bterminad(?:o|a|os|as)\b", r"\bresuelt(?:o|a|os|as)\b", r"\bterminated\b"),
    ),
    (DocumentState.DRAFT, (r"\bborrador(?:es)?\b", r"\bdrafts?\b")),
    (DocumentState.ACTIVE, (r"\bactive\b", r"\bactiv(?:o|a|os|as)\b", r"\bvigente(?:s)?\b")),
)


def resolve_requested_document_state(message: str) -> DocumentState | None:
    """Infer the requested document state from the user's message."""
    normalized = normalize_access_text(message or "")
    return next(
        (document_state for document_state, patterns in STATE_PATTERNS if any(re.search(pattern, normalized) for pattern in patterns)),
        None,
    )
