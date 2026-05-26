"""Utilities for validating template placeholders."""

import itertools
import re
import unicodedata
from collections.abc import Sequence
from typing import ClassVar

from ....documents.domain import DocumentType
from ...domain.entities import TemplateContent
from ...domain.exceptions import TemplateValidationError

EXPRESSION_PATTERN = re.compile(r"{{\s*(.*?)\s*}}")
SIMPLE_PLACEHOLDER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
SUPPORTED_FORMAT_DATE_EXPRESSION_PATTERN = re.compile(
    r"^(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*format_date\s*\(\s*(?P<quote>['\"])(?P<fmt>.*?)\2\s*\)$"
)
CLAUSE_PATTERN = re.compile(r"\*\*(?P<label>[A-ZÁÉÍÓÚÑ ]+?)\.\-\*\*", re.IGNORECASE)
MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(?P<title>.+)$")
NAMED_STRUCTURE_PATTERN = re.compile(
    r"^(?:\*\*)?(?P<prefix>cl[aá]usula|art[ií]culo|secci[oó]n|cap[ií]tulo)\s+(?P<identifier>[A-Z0-9IVXLCM]+(?:\.\d+)*)",
    re.IGNORECASE,
)

CLAUSE_ORDER: dict[str, int] = {
    "PRIMERA": 1,
    "SEGUNDA": 2,
    "TERCERA": 3,
    "CUARTA": 4,
    "QUINTA": 5,
    "SEXTA": 6,
    "SEPTIMA": 7,
    "SETIMA": 7,
    "OCTAVA": 8,
    "NOVENA": 9,
    "DECIMA": 10,
    "DECIMO PRIMERA": 11,
    "DECIMO SEGUNDA": 12,
    "DECIMO TERCERA": 13,
    "DECIMO CUARTA": 14,
    "DECIMO QUINTA": 15,
    "DECIMO SEXTA": 16,
    "DECIMO SEPTIMA": 17,
    "DECIMO OCTAVA": 18,
    "DECIMO NOVENA": 19,
    "VIGESIMA": 20,
}


def extract_supported_placeholder_key(expression: str) -> str | None:
    """Returns the placeholder key from supported expressions."""
    if SIMPLE_PLACEHOLDER_PATTERN.fullmatch(expression):
        return expression
    match = SUPPORTED_FORMAT_DATE_EXPRESSION_PATTERN.fullmatch(expression)
    return None if match is None else match.group("key")


class TemplatePlaceholderValidator:
    MISSING_CONTRACT_DATE_MAPPING_WARNING: ClassVar[str] = "La plantilla no define un mapeo de vigencia del contrato para fecha de inicio y fin."
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
        """Extrae placeholders Jinja simples del markdown."""
        expressions = self._extract_expressions(body_md)
        return {key for expression in expressions if (key := extract_supported_placeholder_key(expression)) is not None}

    def validate(
        self,
        content: TemplateContent,
        *,
        document_type: DocumentType | None = None,
        require_contract_date_mapping: bool = False,
    ) -> list[str]:
        """Valida placeholders y devuelve warnings."""
        expressions = self._extract_expressions(content.body_md)
        if unsupported_expressions := sorted(
            {
                expression
                for expression in expressions
                if extract_supported_placeholder_key(expression) is None
            }
        ):
            raise TemplateValidationError(f"Expresiones Jinja no soportadas: {', '.join(unsupported_expressions)}")

        placeholders = {key for expression in expressions if (key := extract_supported_placeholder_key(expression)) is not None}
        field_keys = {field.key for field in content.fields}
        operational_field_keys = {field.key for field in content.operational_fields}
        allowed_keys = field_keys | self.AUTO_VARIABLES

        unknown = sorted(placeholders - allowed_keys)
        unused = sorted(field_keys - placeholders)

        if unknown:
            raise TemplateValidationError(f"Placeholders no soportados: {', '.join(unknown)}")

        warnings: list[str] = []
        if unused:
            warnings.append(f"Campos definidos pero no usados: {', '.join(unused)}")
        warnings.extend(
            self._validate_contract_date_mapping(
                content=content,
                all_field_keys=field_keys | operational_field_keys,
                document_type=document_type,
                require_contract_date_mapping=require_contract_date_mapping,
            )
        )
        warnings.extend(self._validate_clause_sequence(content.body_md))
        return warnings

    def _validate_contract_date_mapping(
        self,
        *,
        content: TemplateContent,
        all_field_keys: set[str],
        document_type: DocumentType | None,
        require_contract_date_mapping: bool,
    ) -> list[str]:
        mapping = content.contract_date_mapping
        if mapping is None:
            if document_type == DocumentType.COMPANY and require_contract_date_mapping:
                raise TemplateValidationError(self.MISSING_CONTRACT_DATE_MAPPING_WARNING)
            else:
                return (
                    [self.MISSING_CONTRACT_DATE_MAPPING_WARNING]
                    if document_type == DocumentType.COMPANY
                    else []
                )
        if missing_fields := [
            field_key
            for field_key in (mapping.start_date_field, mapping.end_date_field)
            if field_key not in all_field_keys
        ]:
            raise TemplateValidationError("El mapeo de vigencia del contrato referencia campos inexistentes: " + ", ".join(sorted(missing_fields)))
        return []

    def validate_against_reference(self, body_md: str, reference_clause_sequence: Sequence[str]) -> list[str]:
        """Compara el draft contra la secuencia de clausulas de referencia."""
        if not reference_clause_sequence:
            return []

        generated_clause_sequence = self.extract_clause_labels(body_md)
        if missing_clauses := [
            label
            for label in reference_clause_sequence
            if label not in generated_clause_sequence
        ]:
            return [f"Cláusulas de referencia no preservadas: {', '.join(missing_clauses)}"]
        else:
            return []

    def validate_structure_against_reference(self, body_md: str, reference_structure_sequence: Sequence[str]) -> list[str]:
        """Compara el draft contra una secuencia estructural genérica."""
        if not reference_structure_sequence:
            return []

        generated_structure_sequence = self.extract_structure_markers(body_md)
        if missing_markers := [
            marker
            for marker in reference_structure_sequence
            if marker not in generated_structure_sequence
        ]:
            return [f"Estructura de referencia no preservada: {', '.join(missing_markers)}"]
        else:
            return []

    def extract_clause_labels(self, body_md: str) -> list[str]:
        """Extrae etiquetas normalizadas de cláusulas."""
        return [label for _, label, _ in self._extract_clause_sequence(body_md)]

    def extract_structure_markers(self, body_md: str) -> list[str]:
        """Extrae marcadores estructurales genéricos."""
        markers: list[str] = []
        for raw_line in body_md.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if heading_match := MARKDOWN_HEADING_PATTERN.match(line):
                title = heading_match.group("title").strip().strip("*")
                markers.append(f"HEADING:{self._normalize_clause_label(title)}")
                continue

            if named_match := NAMED_STRUCTURE_PATTERN.match(line.strip("*")):
                prefix = self._normalize_clause_label(named_match.group("prefix"))
                identifier = self._normalize_clause_label(named_match.group("identifier"))
                markers.append(f"{prefix}:{identifier}")
                continue

            if clause_match := CLAUSE_PATTERN.search(line):
                label = self._normalize_clause_label(clause_match.group("label"))
                markers.append(f"CLAUSE:{label}")

        return markers

    def _extract_expressions(self, body_md: str) -> list[str]:
        """Extrae expresiones Jinja completas del markdown."""
        return [expression.strip() for expression in EXPRESSION_PATTERN.findall(body_md)]

    def _validate_clause_sequence(self, body_md: str) -> list[str]:
        """Detecta saltos en la numeración de cláusulas."""
        clauses = self._extract_clause_sequence(body_md)
        if len(clauses) < 2:
            return []

        warnings: list[str] = []
        for previous, current in itertools.pairwise(clauses):
            previous_label, _, previous_number = previous
            current_label, _, current_number = current
            if current_number <= previous_number:
                warnings.append(f"Numeración de cláusulas no ascendente: {previous_label} -> {current_label}")
            elif current_number - previous_number > 1:
                warnings.append(f"Numeración de cláusulas con salto: {previous_label} -> {current_label}")
        return warnings

    def _extract_clause_sequence(self, body_md: str) -> list[tuple[str, str, int]]:
        """Extrae la secuencia de cláusulas reconocibles."""
        clauses: list[tuple[str, str, int]] = []
        for line in body_md.splitlines():
            match = CLAUSE_PATTERN.search(line)
            if not match:
                continue

            raw_label = match.group("label").strip()
            normalized_label = self._normalize_clause_label(raw_label)
            clause_number = CLAUSE_ORDER.get(normalized_label)
            if clause_number is None:
                continue
            clauses.append((raw_label, normalized_label, clause_number))
        return clauses

    def _normalize_clause_label(self, label: str) -> str:
        """Normaliza etiquetas de cláusulas para el mapeo."""
        normalized = unicodedata.normalize("NFD", label)
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return re.sub(r"\s+", " ", normalized).strip().upper()
