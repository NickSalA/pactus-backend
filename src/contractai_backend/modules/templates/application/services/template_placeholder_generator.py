"""Application service for generating template placeholders."""

import re
import unicodedata


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

        tokens = TemplatePlaceholderGenerator._field_tokens(key=key, label=label)
        if field_type == "date":
            return "Ej. 2026-12-31"
        if field_type == "time":
            return "Ej. 09:00"
        if tokens & {"literal", "letras"}:
            return "Ej. mil quinientos"
        if "partida" in tokens:
            return "Ej. 11012345"
        if "registro" in tokens:
            return "Ej. Registro de Personas Juridicas de Lima"
        if field_type == "number":
            if "porcentaje" in tokens:
                return "Ej. 10"
            if tokens & {"monto", "valor", "precio", "renta", "retribucion", "remuneracion", "utilidad"}:
                return "Ej. 1500"
            return "Ej. 1000"
        if field_type == "boolean":
            return "Ej. Sí"
        if "ruc" in tokens:
            return "Ej. 20123456789"
        if "dni" in tokens:
            return "Ej. 12345678"
        if "email" in tokens or "correo" in tokens:
            return "Ej. contacto@empresa.com"
        if "telefono" in tokens or "celular" in tokens:
            return "Ej. +51 999 888 777"
        if "domicilio" in tokens or "direccion" in tokens:
            return "Ej. Av. Javier Prado 123, Lima"
        if {"razon", "social"} <= tokens:
            return "Ej. Inversiones Andinas S.A.C."
        if "nombre" in tokens:
            return "Ej. Juan Perez"
        if "moneda" in tokens:
            return "Ej. USD"
        if "jurisdiccion" in tokens or ({"camara", "comercio"} <= tokens):
            return "Ej. Lima"
        if "plazo" in tokens or "duracion" in tokens:
            return "Ej. 12 meses"
        if "objeto" in tokens:
            return "Ej. Administracion integral del hotel"
        return f"Ej. {label}"

    @staticmethod
    def should_autogenerate_placeholder(placeholder: str | None) -> bool:
        """Determines if a placeholder is missing or invalid."""
        if placeholder is None:
            return True
        normalized = unicodedata.normalize("NFD", placeholder)
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        normalized = normalized.strip().lower()
        return normalized.startswith(
            (
                "ingrese",
                "introduzca",
                "escriba",
                "seleccione",
                "indique",
                "coloque",
                "digite",
                "consigne",
            )
        )

    @staticmethod
    def _field_tokens(*, key: str, label: str) -> set[str]:
        """Extracts normalized tokens from a field's key and label."""
        normalized = unicodedata.normalize("NFD", key + " " + label)
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
        return {token for token in normalized.split("_") if token}
