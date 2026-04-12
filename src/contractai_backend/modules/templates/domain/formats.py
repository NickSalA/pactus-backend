"""Template format catalog and helpers."""

import re
from dataclasses import dataclass

from ...documents.domain import DocumentType

FORMAT_CODE_PATTERN: re.Pattern[str] = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


@dataclass(frozen=True)
class TemplateFormatDefinition:
    """Describes one supported template format."""

    document_type: DocumentType
    format_code: str
    label: str


TEMPLATE_FORMATS_BY_DOCUMENT_TYPE: dict[DocumentType, tuple[TemplateFormatDefinition, ...]] = {
    DocumentType.COMPANY: (
        TemplateFormatDefinition(document_type=DocumentType.COMPANY, format_code="management", label="Contrato de Management"),
        TemplateFormatDefinition(document_type=DocumentType.COMPANY, format_code="service_agreement", label="Contrato de Servicios"),
        TemplateFormatDefinition(document_type=DocumentType.COMPANY, format_code="nda", label="Acuerdo de Confidencialidad"),
    ),
    DocumentType.LABOR: (
        TemplateFormatDefinition(document_type=DocumentType.LABOR, format_code="fixed_term", label="Contrato a Plazo Fijo"),
        TemplateFormatDefinition(document_type=DocumentType.LABOR, format_code="indefinite_term", label="Contrato Indefinido"),
        TemplateFormatDefinition(document_type=DocumentType.LABOR, format_code="internship", label="Convenio de Practicas"),
    ),
}


def normalize_format_code(value: str) -> str:
    """Normalizes and validates a template format code."""
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"_+", "_", normalized)
    if not normalized or not FORMAT_CODE_PATTERN.fullmatch(normalized):
        raise ValueError("format_code must be a lowercase slug using letters, numbers and underscores")
    return normalized


def list_template_formats(document_type: DocumentType | None = None) -> list[TemplateFormatDefinition]:
    """Lists template formats for one document type or all of them."""
    if document_type is not None:
        return list(TEMPLATE_FORMATS_BY_DOCUMENT_TYPE.get(document_type, ()))

    formats: list[TemplateFormatDefinition] = []
    for definitions in TEMPLATE_FORMATS_BY_DOCUMENT_TYPE.values():
        formats.extend(definitions)
    return formats


def is_valid_template_format(document_type: DocumentType, format_code: str) -> bool:
    """Checks whether a format code belongs to the given document type."""
    normalized = normalize_format_code(format_code)
    return any(definition.format_code == normalized for definition in TEMPLATE_FORMATS_BY_DOCUMENT_TYPE.get(document_type, ()))
