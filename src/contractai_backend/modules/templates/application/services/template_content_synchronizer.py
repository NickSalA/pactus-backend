"""Synchronizes template fields with the markdown placeholders."""

import re
import unicodedata
from typing import ClassVar

from ...domain.entities import TemplateContent, TemplateContractDateMapping, TemplateField
from .template_placeholder_generator import TemplatePlaceholderGenerator
from .template_placeholder_validator import (
    EXPRESSION_PATTERN,
    TemplatePlaceholderValidator,
    extract_supported_placeholder_key,
)


class TemplateContentSynchronizer:
    """Keeps template fields aligned with body_md placeholders."""

    BRACKET_PLACEHOLDER_PATTERN = re.compile(r"\[([^\[\]\n]{2,200})\]")
    TIME_PLACEHOLDER_PATTERN = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d(?:\s?(?:AM|PM|am|pm))?$")
    MARKDOWN_IMAGE_PATTERN = re.compile(r"^\s*!\[[^\]]*\]\([^\)]+\)\s*$", re.MULTILINE)
    REFERENCE_IMAGE_ARTIFACT_PATTERN = re.compile(r"^\s*!{{[^{}\n]+}}\([^\)]+\)\s*$", re.MULTILINE)
    LEGACY_DATE_FILTER_PATTERN = re.compile(r"{{\s*(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*date\s*:\s*(?P<quote>['\"])(?P<fmt>.*?)\2\s*}}")
    SHORTHAND_DATE_FILTER_PATTERN = re.compile(r"{{\s*(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*date\s*\(\s*(?P<quote>['\"])(?P<fmt>.*?)\2\s*\)\s*}}")
    DATE_COMPONENT_FILTER_PATTERN = re.compile(r"{{\s*(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*(?P<component>day|month|year)\s*}}")
    IGNORED_BRACKET_MARKERS: frozenset[str] = frozenset({"cierre_documento"})
    AUTO_VARIABLE_ALIASES: ClassVar[dict[str, str]] = {
        "representante_nombre_empresa": "representante_nombre",
        "representante_nombre_empleador": "representante_nombre",
        "representante_dni_empresa": "representante_dni",
        "representante_dni_empleador": "representante_dni",
        "ruc_empresa": "empleador_ruc",
        "empresa_ruc": "empleador_ruc",
        "razon_social_empresa": "empleador_razon_social",
        "empresa_razon_social": "empleador_razon_social",
        "domicilio_empresa": "empleador_domicilio",
        "empresa_domicilio": "empleador_domicilio",
        "objeto_social_empresa": "empleador_objeto_social",
        "empresa_objeto_social": "empleador_objeto_social",
        "empleador_tipo_sociedad": "empleador_descripcion",
        "tipo_sociedad_empresa": "empleador_descripcion",
    }
    MANUAL_FIELD_ALIASES: ClassVar[dict[str, str]] = {
        "remuneracion_mensual_fija": "remuneracion_mensual",
    }
    PLACEHOLDER_KEY_ALIASES: ClassVar[dict[str, str]] = {
        **AUTO_VARIABLE_ALIASES,
        **MANUAL_FIELD_ALIASES,
    }

    START_DATE_KEYS: tuple[str, ...] = (
        "contrato_fecha_inicio",
        "contract_start_date",
        "fecha_inicio",
        "start_date",
    )
    END_DATE_KEYS: tuple[str, ...] = (
        "contrato_fecha_fin",
        "contract_end_date",
        "fecha_fin",
        "end_date",
    )
    CONTRACT_DATE_HINTS: frozenset[str] = frozenset({"contrato", "contract", "vigencia", "plazo", "periodo"})
    START_DATE_HINTS: frozenset[str] = frozenset({"inicio", "start", "desde", "inicial", "comienzo", "inicio_real"})
    END_DATE_HINTS: frozenset[str] = frozenset({"fin", "end", "hasta", "final", "termino", "terminacion", "vencimiento"})
    DATE_VALUE_HINTS: frozenset[str] = frozenset({"fecha", "date"})
    SERVICE_HINTS: frozenset[str] = frozenset({"servicio", "service", "prestacion", "item"})

    def sync(self, content: TemplateContent) -> TemplateContent:
        """Rebuilds fields from the placeholders present in body_md."""
        normalized_body_md = self._normalize_reference_markers(content.body_md)
        expressions = [expression.strip() for expression in EXPRESSION_PATTERN.findall(normalized_body_md)]
        unsupported_expressions = sorted({expression for expression in expressions if extract_supported_placeholder_key(expression) is None})
        if unsupported_expressions:
            raise ValueError(f"Expresiones Jinja no soportadas: {', '.join(unsupported_expressions)}")

        ordered_manual_keys = self._extract_manual_keys(expressions)
        normalized_mapping = self._normalize_contract_date_mapping(content.contract_date_mapping)
        visible_fields = self._filter_auto_variable_fields(self._normalize_field_group(content.fields))
        operational_fields = self._filter_auto_variable_fields(self._normalize_field_group(content.operational_fields))
        existing_fields = self._merge_existing_fields(
            visible_fields,
            operational_fields,
            visible_keys=ordered_manual_keys,
        )
        resolved_mapping = normalized_mapping or self._infer_contract_date_mapping(list(existing_fields.values()))
        mapping_keys = self._extract_contract_date_mapping_keys(resolved_mapping)

        synced_fields: list[TemplateField] = []
        for key in ordered_manual_keys:
            field = existing_fields.get(key)
            if field is not None:
                synced_fields.append(self._normalize_visible_field(field, is_contract_date_field=key in mapping_keys))
                continue
            synced_fields.append(self._build_default_field(key))

        synced_operational_fields = self._build_operational_fields(
            existing_fields=existing_fields,
            original_operational_fields=operational_fields,
            visible_keys=ordered_manual_keys,
            mapping_keys=mapping_keys,
        )

        inferred_mapping = resolved_mapping or self._infer_contract_date_mapping(
            synced_fields + synced_operational_fields,
        )

        return TemplateContent(
            body_md=normalized_body_md,
            fields=synced_fields,
            operational_fields=synced_operational_fields,
            version=content.version,
            contract_date_mapping=inferred_mapping,
        )

    def _filter_auto_variable_fields(self, fields: list[TemplateField]) -> list[TemplateField]:
        """Drops organization auto variables from user-editable field groups."""
        return [field for field in fields if field.key not in TemplatePlaceholderValidator.AUTO_VARIABLES]

    def _normalize_field_group(self, fields: list[TemplateField]) -> list[TemplateField]:
        """Canonicalizes known field aliases before synchronization."""
        normalized_fields: list[TemplateField] = []
        for field in fields:
            normalized_key = self._canonicalize_placeholder_key(field.key)
            if normalized_key == field.key:
                normalized_fields.append(field)
                continue
            normalized_fields.append(field.model_copy(update={"key": normalized_key}))
        return normalized_fields

    def _normalize_contract_date_mapping(
        self,
        mapping: TemplateContractDateMapping | None,
    ) -> TemplateContractDateMapping | None:
        """Canonicalizes mapping keys when they use supported aliases."""
        if mapping is None:
            return None
        start_date_field = self._canonicalize_placeholder_key(mapping.start_date_field)
        end_date_field = self._canonicalize_placeholder_key(mapping.end_date_field)
        if start_date_field == mapping.start_date_field and end_date_field == mapping.end_date_field:
            return mapping
        return TemplateContractDateMapping(start_date_field=start_date_field, end_date_field=end_date_field)

    def _normalize_reference_markers(self, body_md: str) -> str:
        """Converts reference markers like [NOMBRE CAMPO] into Jinja placeholders."""

        def replace_marker(match: re.Match[str]) -> str:
            raw_marker = match.group(1).strip()
            marker_key = self._build_reference_marker_key(raw_marker)
            if marker_key in self.IGNORED_BRACKET_MARKERS:
                return ""
            return "{{ " + marker_key + " }}"

        normalized_body_md = self._remove_reference_artifacts(body_md)
        normalized_body_md = self.BRACKET_PLACEHOLDER_PATTERN.sub(replace_marker, normalized_body_md)
        normalized_body_md = self._canonicalize_placeholder_aliases(normalized_body_md)
        normalized_body_md = self._normalize_supported_jinja_filters(normalized_body_md)
        return re.sub(r"\n{3,}", "\n\n", normalized_body_md)

    def _remove_reference_artifacts(self, body_md: str) -> str:
        """Removes markdown image artifacts copied from source documents."""
        normalized_body_md = self.MARKDOWN_IMAGE_PATTERN.sub("", body_md)
        normalized_body_md = self.REFERENCE_IMAGE_ARTIFACT_PATTERN.sub("", normalized_body_md)
        return normalized_body_md

    def _normalize_supported_jinja_filters(self, body_md: str) -> str:
        """Normalizes legacy date filters to the supported format_date filter."""
        normalized_body_md = self.LEGACY_DATE_FILTER_PATTERN.sub(self._build_format_date_placeholder, body_md)
        normalized_body_md = self.SHORTHAND_DATE_FILTER_PATTERN.sub(self._build_format_date_placeholder, normalized_body_md)
        normalized_body_md = self.DATE_COMPONENT_FILTER_PATTERN.sub(self._build_date_component_placeholder, normalized_body_md)
        return normalized_body_md

    def _build_format_date_placeholder(self, match: re.Match[str]) -> str:
        """Builds a canonical format_date placeholder from regex matches."""
        return "{{ " + match.group("key") + " | format_date('" + match.group("fmt") + "') }}"

    def _build_date_component_placeholder(self, match: re.Match[str]) -> str:
        """Builds a canonical format_date placeholder from date component filters."""
        date_formats = {"day": "%d", "month": "%m", "year": "%Y"}
        return "{{ " + match.group("key") + " | format_date('" + date_formats[match.group("component")] + "') }}"

    def _canonicalize_placeholder_aliases(self, body_md: str) -> str:
        """Replaces known placeholder aliases with their canonical keys."""
        normalized_body_md = body_md
        for alias, canonical_key in self.PLACEHOLDER_KEY_ALIASES.items():
            pattern = re.compile(r"{{\s*" + re.escape(alias) + r"\s*}}")
            normalized_body_md = pattern.sub("{{ " + canonical_key + " }}", normalized_body_md)
        return normalized_body_md

    def _canonicalize_placeholder_key(self, key: str) -> str:
        """Returns the canonical key for supported aliases."""
        return self.PLACEHOLDER_KEY_ALIASES.get(key, key)

    def _build_reference_marker_key(self, raw_marker: str) -> str:
        """Builds a stable snake_case key from a bracket marker."""
        normalized_marker = self._normalize_text(raw_marker)
        stopwords = {"de", "del", "la", "las", "el", "los", "o", "u", "y", "para", "por", "en", "a"}
        tokens = [token for token in normalized_marker.split("_") if token and token not in stopwords]
        collapsed_key = "_".join(tokens) or normalized_marker or "campo_referencia"
        return collapsed_key

    def _build_operational_fields(
        self,
        *,
        existing_fields: dict[str, TemplateField],
        original_operational_fields: list[TemplateField],
        visible_keys: list[str],
        mapping_keys: list[str],
    ) -> list[TemplateField]:
        """Builds backend-only fields without polluting body_md fields."""
        visible_key_set = set(visible_keys)
        operational_keys = [field.key for field in original_operational_fields if field.key not in visible_key_set]
        for key in mapping_keys:
            if key not in visible_key_set and key not in operational_keys:
                operational_keys.append(key)

        operational_fields: list[TemplateField] = []
        for key in operational_keys:
            field = existing_fields.get(key)
            if field is not None:
                operational_fields.append(self._normalize_operational_field(field, is_contract_date_field=key in mapping_keys))
                continue
            field_type = "date" if key in mapping_keys else "text"
            operational_fields.append(self._build_default_field(key, field_type=field_type))
        return operational_fields

    def _normalize_visible_field(self, field: TemplateField, *, is_contract_date_field: bool) -> TemplateField:
        """Visible placeholders are always required because they render directly in the contract body."""
        updates: dict[str, str | bool] = {"required": True}
        inferred_type = "date" if is_contract_date_field else self._normalize_existing_field_type(field)
        if inferred_type != field.type:
            updates["type"] = inferred_type
        resolved_type = str(updates.get("type", field.type))
        if TemplatePlaceholderGenerator.should_autogenerate_placeholder(field.placeholder) or resolved_type != field.type:
            updates["placeholder"] = TemplatePlaceholderGenerator.build_placeholder(
                key=field.key,
                label=field.label,
                field_type=resolved_type,
            )
        return TemplateField.model_validate({**field.model_dump(), **updates})

    def _normalize_operational_field(self, field: TemplateField, *, is_contract_date_field: bool) -> TemplateField:
        """Contract-date operational fields must stay required and typed as dates."""
        updates: dict[str, str | bool] = {}
        inferred_type = "date" if is_contract_date_field else self._normalize_existing_field_type(field)
        if is_contract_date_field:
            updates["required"] = True
        if inferred_type != field.type:
            updates["type"] = inferred_type
        resolved_type = str(updates.get("type", field.type))
        if TemplatePlaceholderGenerator.should_autogenerate_placeholder(field.placeholder) or resolved_type != field.type:
            updates["placeholder"] = TemplatePlaceholderGenerator.build_placeholder(
                key=field.key,
                label=field.label,
                field_type=resolved_type,
            )
        return field if not updates else TemplateField.model_validate({**field.model_dump(), **updates})

    def _normalize_existing_field_type(self, field: TemplateField) -> str:
        """Fixes obvious type mismatches returned by the draft generator."""
        inferred_type = self._infer_field_type(field.key, field.label, field.placeholder)
        if field.type in {"text", "number"} and inferred_type != field.type:
            return inferred_type
        return field.type

    def _merge_existing_fields(
        self,
        fields: list[TemplateField],
        operational_fields: list[TemplateField],
        *,
        visible_keys: list[str],
    ) -> dict[str, TemplateField]:
        """Indexes fields and resolves duplicated keys across both groups."""
        indexed_fields = self._index_fields(fields)
        indexed_operational_fields = self._index_fields(operational_fields)
        overlapping_keys = sorted(set(indexed_fields) & set(indexed_operational_fields))

        visible_key_set = set(visible_keys)
        for key in overlapping_keys:
            if key in visible_key_set:
                indexed_operational_fields.pop(key, None)
                continue
            indexed_fields.pop(key, None)

        return {**indexed_operational_fields, **indexed_fields}

    def _infer_contract_date_mapping(self, fields: list[TemplateField]) -> TemplateContractDateMapping | None:
        """Infers contract date fields when placeholders are semantically clear."""
        start_date_field = self._find_exact_field_key(fields, self.START_DATE_KEYS) or self._select_best_field_key(
            fields,
            boundary_hints=self.START_DATE_HINTS,
            opposite_hints=self.END_DATE_HINTS,
        )
        end_date_field = self._find_exact_field_key(fields, self.END_DATE_KEYS) or self._select_best_field_key(
            fields,
            boundary_hints=self.END_DATE_HINTS,
            opposite_hints=self.START_DATE_HINTS,
        )
        if start_date_field is None or end_date_field is None or start_date_field == end_date_field:
            return None
        return TemplateContractDateMapping(start_date_field=start_date_field, end_date_field=end_date_field)

    def _find_exact_field_key(self, fields: list[TemplateField], allowed_keys: tuple[str, ...]) -> str | None:
        allowed = set(allowed_keys)
        for field in fields:
            if field.key in allowed:
                return field.key
        return None

    def _select_best_field_key(
        self,
        fields: list[TemplateField],
        *,
        boundary_hints: frozenset[str],
        opposite_hints: frozenset[str],
    ) -> str | None:
        scored_candidates: list[tuple[int, str]] = []
        for field in fields:
            score = self._score_contract_date_field(field, boundary_hints=boundary_hints, opposite_hints=opposite_hints)
            if score is None:
                continue
            scored_candidates.append((score, field.key))

        if not scored_candidates:
            return None

        best_score = max(score for score, _ in scored_candidates)
        best_keys = sorted({key for score, key in scored_candidates if score == best_score})
        if len(best_keys) != 1:
            return None
        return best_keys[0]

    def _score_contract_date_field(
        self,
        field: TemplateField,
        *,
        boundary_hints: frozenset[str],
        opposite_hints: frozenset[str],
    ) -> int | None:
        tokens = self._tokenize_field(field)
        if not tokens or not (tokens & boundary_hints):
            return None

        has_contract_context = bool(tokens & self.CONTRACT_DATE_HINTS)
        has_service_context = bool(tokens & self.SERVICE_HINTS)
        if has_service_context and not has_contract_context:
            return None

        score = 0
        if has_contract_context:
            score += 10
        if tokens & self.DATE_VALUE_HINTS:
            score += 3
        if field.type == "date":
            score += 2
        if not tokens & opposite_hints:
            score += 1
        return score

    def _tokenize_field(self, field: TemplateField) -> set[str]:
        normalized_key = self._normalize_text(field.key)
        normalized_label = self._normalize_text(field.label)
        return {token for token in (normalized_key + "_" + normalized_label).split("_") if token}

    def _normalize_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFD", value)
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
        return normalized

    def _extract_manual_keys(self, expressions: list[str]) -> list[str]:
        """Returns manual placeholders in first-appearance order."""
        ordered_keys: list[str] = []
        seen_keys: set[str] = set()

        for expression in expressions:
            key = extract_supported_placeholder_key(expression)
            if key is None or key in TemplatePlaceholderValidator.AUTO_VARIABLES or key in seen_keys:
                continue
            ordered_keys.append(key)
            seen_keys.add(key)

        return ordered_keys

    def _extract_contract_date_mapping_keys(self, mapping: TemplateContractDateMapping | None) -> list[str]:
        """Returns contract date mapping keys in a stable order."""
        if mapping is None:
            return []
        return [mapping.start_date_field, mapping.end_date_field]

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

    def _build_default_field(self, key: str, *, field_type: str = "text") -> TemplateField:
        """Builds a default field for a new placeholder."""
        label = self._humanize_key(key)
        resolved_field_type = self._infer_field_type(key, label, None) if field_type == "text" else field_type
        placeholder = TemplatePlaceholderGenerator.build_placeholder(key=key, label=label, field_type=resolved_field_type)
        return TemplateField(
            key=key,
            label=label,
            type=resolved_field_type,
            required=True,
            placeholder=placeholder,
        )

    def _infer_field_type(self, key: str, label: str, placeholder: str | None) -> str:
        """Infers a sensible field type from key and label semantics."""
        tokens = self._tokenize_field(TemplateField(key=key, label=label, placeholder=placeholder))
        if tokens & {"literal", "letras"}:
            return "text"
        if placeholder and self.TIME_PLACEHOLDER_PATTERN.fullmatch(placeholder.strip()):
            return "time"
        if tokens & {"hora", "horario"} and not tokens & {"duracion", "dias", "laborales"}:
            return "time"
        if tokens & {"ingreso", "salida", "entrada"}:
            return "time"
        if "refrigerio" in tokens and tokens & {"inicio", "fin"}:
            return "time"
        if "fecha" in tokens or key.endswith("_date"):
            return "date"
        if tokens & {"numero", "cantidad", "monto", "porcentaje", "valor", "retribucion", "remuneracion", "utilidad"}:
            return "number"
        return "text"

    def _humanize_key(self, key: str) -> str:
        """Builds a human-readable label from a placeholder key."""
        return key.replace("_", " ").strip().capitalize()
