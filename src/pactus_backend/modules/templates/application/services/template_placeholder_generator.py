"""Application service for generating template placeholders."""

from .....shared.text import remove_accents
from ...domain.patterns import INSTRUCTIONAL_PLACEHOLDER_PREFIXES


class TemplatePlaceholderGenerator:
    """Generates standard placeholders for template fields."""

    @staticmethod
    def build_placeholder(*, key: str, label: str, field_type: str) -> str:
        """Builds a UI-friendly placeholder text for a given field."""
        canonical_examples = {
            "trabajador_nombre": "Ej. Juan Perez",
            "cliente_nombre": "Ej. Empresa S.A.C.",
            "cliente_ruc": "Ej. 20123456789",
            "trabajador_dni": "Ej. 12345678",
            "cargo": "Ej. Desarrollador",
            "salario": "Ej. 1500",
            "moneda": "Ej. USD",
            "periodicidad": "Ej. MENSUAL",
            "modalidad": "Ej. Indeterminado",
        }
        if key in canonical_examples:
            return canonical_examples[key]

        normalized_key = key.lower()
        if "dni" in normalized_key:
            return "Ej. 12345678"
        if "ruc" in normalized_key:
            return "Ej. 20123456789"

        if field_type == "date":
            return "Ej. 2026-12-31"
        if field_type == "time":
            return "Ej. 09:00"
        if field_type == "number":
            return "Ej. 1000"
        if field_type == "boolean":
            return "Ej. Sí"

        return f"Ej. {label}"

    @staticmethod
    def should_autogenerate_placeholder(placeholder: str | None) -> bool:
        """Determines if a placeholder is missing or invalid."""
        if placeholder is None:
            return True
        normalized = remove_accents(placeholder).strip().lower()
        return normalized.startswith(INSTRUCTIONAL_PLACEHOLDER_PREFIXES)
