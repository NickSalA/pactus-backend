"""Utilities for validating template placeholders."""

import re
from typing import ClassVar

from ...domain.entities import TemplateContent

PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class TemplatePlaceholderValidator:
    AUTO_VARIABLES: ClassVar[frozenset[str]] = frozenset(
        {
            "empleador_razon_social",
            "empleador_ruc",
            "empleador_domicilio",
            "empleador_descripcion",
            "empleador_objeto_social",
            "representante_nombre",
            "representante_dni",
            "jurisdiccion",
            "lugar_firma",
            "autorizacion_entidad",
            "autorizacion_fecha",
            "autorizacion_emitida_por",
            "empleador_email",
            "empleador_telefono",
            "day_sign",
            "month_sign",
            "year_sign",
        }
    )

    def extract(self, body_md: str) -> set[str]:
        """Extrae placeholders Jinja del markdown."""
        return set(PLACEHOLDER_PATTERN.findall(body_md))

    def validate(self, content: TemplateContent) -> list[str]:
        """Valida placeholders y devuelve warnings."""
        placeholders = self.extract(content.body_md)
        field_keys = {field.key for field in content.fields}
        allowed_keys = field_keys | self.AUTO_VARIABLES

        unknown = sorted(placeholders - allowed_keys)
        unused = sorted(field_keys - placeholders)

        if unknown:
            raise ValueError(f"Placeholders no soportados: {', '.join(unknown)}")

        warnings: list[str] = []
        if unused:
            warnings.append(f"Campos definidos pero no usados: {', '.join(unused)}")
        return warnings
