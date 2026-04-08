"""Synchronizes template fields with the markdown placeholders."""

from ...domain.entities import TemplateContent, TemplateField
from .template_placeholder_validator import EXPRESSION_PATTERN, SIMPLE_PLACEHOLDER_PATTERN, TemplatePlaceholderValidator


class TemplateContentSynchronizer:
    """Keeps template fields aligned with body_md placeholders."""

    def sync(self, content: TemplateContent) -> TemplateContent:
        """Rebuilds fields from the placeholders present in body_md."""
        expressions = [expression.strip() for expression in EXPRESSION_PATTERN.findall(content.body_md)]
        unsupported_expressions = sorted({expression for expression in expressions if not SIMPLE_PLACEHOLDER_PATTERN.fullmatch(expression)})
        if unsupported_expressions:
            raise ValueError(f"Expresiones Jinja no soportadas: {', '.join(unsupported_expressions)}")

        existing_fields = self._index_fields(content.fields)
        ordered_manual_keys = self._extract_manual_keys(expressions)

        synced_fields: list[TemplateField] = []
        for key in ordered_manual_keys:
            synced_fields.append(existing_fields.get(key) or self._build_default_field(key))

        return TemplateContent(
            body_md=content.body_md,
            fields=synced_fields,
            version=content.version,
        )

    def _extract_manual_keys(self, expressions: list[str]) -> list[str]:
        """Returns manual placeholders in first-appearance order."""
        ordered_keys: list[str] = []
        seen_keys: set[str] = set()

        for expression in expressions:
            if expression in TemplatePlaceholderValidator.AUTO_VARIABLES or expression in seen_keys:
                continue
            ordered_keys.append(expression)
            seen_keys.add(expression)

        return ordered_keys

    def _index_fields(self, fields: list[TemplateField]) -> dict[str, TemplateField]:
        """Indexes fields by key and rejects duplicates."""
        indexed_fields: dict[str, TemplateField] = {}
        duplicate_keys: set[str] = set()

        for field in fields:
            if field.key in indexed_fields:
                duplicate_keys.add(field.key)
                continue
            indexed_fields[field.key] = field

        if duplicate_keys:
            duplicates = ", ".join(sorted(duplicate_keys))
            raise ValueError(f"Field keys duplicados: {duplicates}")

        return indexed_fields

    def _build_default_field(self, key: str) -> TemplateField:
        """Builds a default field for a new placeholder."""
        return TemplateField(
            key=key,
            label=self._humanize_key(key),
            type="text",
            required=True,
        )

    def _humanize_key(self, key: str) -> str:
        """Builds a human-readable label from a placeholder key."""
        return key.replace("_", " ").strip().capitalize()
