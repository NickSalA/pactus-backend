"""GPT-based template draft generator."""

import json
import re
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from ....shared.config import settings
from ..application.dto import GenerateTemplateDraftRequest, TemplateDraftResponse, TemplateUsage
from ..application.repositories.base_draft_generator import ITemplateDraftGenerator
from ..application.services.template_placeholder_generator import TemplatePlaceholderGenerator


class GeminiTemplateDraftGenerator(ITemplateDraftGenerator):
    TIME_PLACEHOLDER_PATTERN = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d(?:\s?(?:AM|PM|am|pm))?$")

    def __init__(self):
        """Configura el cliente Gemini."""
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL_NAME,
            api_key=settings.GEMINI_API_KEY,
            temperature=settings.MODEL_TEMPERATURE,
            max_retries=0,
        )

    async def generate(
        self,
        request: GenerateTemplateDraftRequest,
        reference_context: str | None = None,
        reference_outline: dict[str, Any] | None = None,
        organization_context: dict[str, Any] | None = None,
        validation_feedback: list[str] | None = None,
    ) -> TemplateDraftResponse:
        """Genera un borrador de plantilla a partir de instrucciones y, opcionalmente, un contrato de referencia."""
        prompt = self._build_prompt(
            request=request,
            reference_context=reference_context,
            reference_outline=reference_outline,
            organization_context=organization_context,
            validation_feedback=validation_feedback,
        )
        response = await self.llm.ainvoke(prompt)

        raw_content: Any = response.content if hasattr(response, "content") else response
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            parts: list[str] = []
            for item in raw_content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    parts.append(text if isinstance(text, str) else str(item))
                else:
                    parts.append(str(item))
            content = "\n".join(parts)
        else:
            content = str(raw_content)

        payload = self._parse_json(content)
        self._ensure_placeholders(payload)
        field_issues = self._detect_raw_field_issues(payload)
        if field_issues:
            source = payload.get("source")
            if not isinstance(source, dict):
                source = {}
                payload["source"] = source
            source["field_issues"] = field_issues
        usage = self._extract_usage(response)
        if usage is not None:
            payload["usage"] = usage.model_dump()
        return TemplateDraftResponse.model_validate(payload)

    def _parse_json(self, raw: str) -> dict[str, Any]:
        """Extrae el JSON valido desde la respuesta del LLM."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            lines = cleaned.splitlines()
            if lines and lines[0].strip().lower() == "json":
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start == -1 or end == -1 or start >= end:
                raise ValueError("LLM response is not valid JSON.") from None
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as exc:
                raise ValueError(f"LLM response is not valid JSON: {exc}") from exc

    def _extract_usage(self, response: Any) -> TemplateUsage | None:
        """Extrae el uso de tokens de la respuesta del modelo."""
        usage_metadata = getattr(response, "usage_metadata", None)
        if not usage_metadata:
            return None

        input_tokens = int(usage_metadata.get("input_tokens", 0))
        output_tokens = int(usage_metadata.get("output_tokens", 0))
        total_tokens = int(usage_metadata.get("total_tokens", input_tokens + output_tokens))
        return TemplateUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    def _ensure_placeholders(self, payload: dict[str, Any]) -> None:
        """Fills missing or invalid placeholders in the draft output before validation."""
        content = payload.get("content")
        if not isinstance(content, dict):
            return

        for group_name in ("fields", "operational_fields"):
            fields = content.get(group_name)
            if not isinstance(fields, list):
                continue
            for raw_field in fields:
                if not isinstance(raw_field, dict):
                    continue
                key = str(raw_field.get("key") or "").strip()
                label = str(raw_field.get("label") or key).strip()
                field_type = str(raw_field.get("type") or "text").strip().lower()
                placeholder = raw_field.get("placeholder")
                placeholder_str = str(placeholder).strip() if isinstance(placeholder, str) else None

                if TemplatePlaceholderGenerator.should_autogenerate_placeholder(placeholder_str):
                    raw_field["placeholder"] = TemplatePlaceholderGenerator.build_placeholder(
                        key=key,
                        label=label,
                        field_type=field_type,
                    )

    def _detect_raw_field_issues(self, payload: dict[str, Any]) -> list[str]:
        """Detects semantic field issues before backend normalization hides them."""
        content = payload.get("content")
        if not isinstance(content, dict):
            return []

        issues: list[str] = []
        for group_name in ("fields", "operational_fields"):
            fields = content.get(group_name)
            if not isinstance(fields, list):
                continue
            for raw_field in fields:
                if not isinstance(raw_field, dict):
                    continue
                issues.extend(self._detect_single_field_issues(raw_field))
        return issues

    def _detect_single_field_issues(self, raw_field: dict[str, Any]) -> list[str]:
        """Detects issues for one raw field definition."""
        key = str(raw_field.get("key") or "").strip()
        label = str(raw_field.get("label") or key).strip()
        field_type = str(raw_field.get("type") or "text").strip().lower()
        placeholder_value = raw_field.get("placeholder")
        placeholder = str(placeholder_value).strip() if isinstance(placeholder_value, str) else None
        if not key:
            return []

        tokens = self._field_tokens(key=key, label=label)
        issues: list[str] = []
        if tokens & {"literal", "letras"} and field_type != "text":
            issues.append(f"El campo '{key}' debe usar type='text' porque representa un valor en letras.")
        if tokens & {"dni", "ruc"} and field_type != "text":
            issues.append(f"El campo '{key}' debe usar type='text' porque es un identificador, no un número para calcular.")
        if self._looks_like_time_field(tokens=tokens, key=key, placeholder=placeholder) and field_type != "time":
            issues.append(f"El campo '{key}' debe usar type='time' porque representa una hora puntual.")
        if placeholder and self._is_instructional_placeholder(placeholder):
            issues.append(f"El campo '{key}' debe usar un placeholder de ejemplo con 'Ej.' y no texto instruccional.")
        return issues

    def _field_tokens(self, *, key: str, label: str) -> set[str]:
        """Builds normalized tokens from a field key and label."""
        normalized = re.sub(r"[^a-z0-9]+", "_", (key + " " + label).lower()).strip("_")
        return {token for token in normalized.split("_") if token}

    def _looks_like_time_field(self, *, tokens: set[str], key: str, placeholder: str | None) -> bool:
        """Detects whether a raw field semantically represents a time value."""
        if placeholder and self.TIME_PLACEHOLDER_PATTERN.fullmatch(placeholder):
            return True
        if tokens & {"hora", "horario"} and not tokens & {"duracion", "dias", "laborales"}:
            return True
        if tokens & {"ingreso", "salida", "entrada"}:
            return True
        if "refrigerio" in tokens and tokens & {"inicio", "fin"}:
            return True
        return key.endswith("_time")

    def _is_instructional_placeholder(self, placeholder: str) -> bool:
        """Detects placeholders that instruct the user instead of showing an example."""
        normalized = placeholder.strip().lower()
        return normalized.startswith(("ingrese", "introduzca", "escriba", "seleccione", "indique", "coloque", "digite", "consigne"))

    def _build_prompt(
        self,
        request: GenerateTemplateDraftRequest,
        reference_context: str | None = None,
        reference_outline: dict[str, Any] | None = None,
        organization_context: dict[str, Any] | None = None,
        validation_feedback: list[str] | None = None,
    ) -> str:
        """Construye el prompt final para GPT."""
        instructions = request.instructions or ""
        name_hint = request.name or ""
        description_hint = request.description or ""
        document_type = request.document_type.value if request.document_type is not None else ""
        format_code = request.format_code
        jurisdiction = request.jurisdiction or ""
        generation_mode = request.generation_mode.value

        reference_section = ""
        if reference_context:
            reference_section = "\nREFERENCE_CONTEXT:\n" + reference_context[:8000]

        reference_outline_section = ""
        if reference_outline:
            reference_outline_section = "\nREFERENCE_OUTLINE:\n" + json.dumps(reference_outline, ensure_ascii=True, indent=2)

        organization_section = ""
        if organization_context:
            organization_section = "\nORGANIZATION_CONTEXT:\n" + json.dumps(organization_context, ensure_ascii=True, indent=2)

        feedback_section = ""
        if validation_feedback:
            feedback_lines = "\n".join(f"- {issue}" for issue in validation_feedback)
            feedback_section = "\nVALIDATION_FEEDBACK:\n" + feedback_lines

        domain_rules = ""
        if document_type == "COMPANY":
            domain_rules = (
                "- IMPORTANT: You MUST use the following canonical keys for client data: 'cliente_nombre', 'cliente_ruc', 'cliente_domicilio', 'representante_cliente'.\n"
                "- For financial data, use 'monto_retribucion' and 'moneda'.\n"
                "- For dates, use 'fecha_inicio' and 'fecha_fin'.\n"
                "- If the reference document does not explicitly state the client's RUC or name, you MUST add 'cliente_nombre' and 'cliente_ruc' to content.operational_fields so the backend can collect them.\n"
            )
        elif document_type == "LABOR":
            domain_rules = (
                "- IMPORTANT: You MUST use the following canonical keys for the employee: 'trabajador_nombre', 'trabajador_dni', 'trabajador_domicilio'.\n"
                "- For the job role, use 'cargo'.\n"
                "- For the remuneration, ALWAYS use 'salario' (must be type number), 'moneda' (PEN/USD), and 'periodicidad' (e.g. MENSUAL).\n"
                "- For the contract type, use 'modalidad'.\n"
                "- For dates, use 'fecha_inicio' and 'fecha_fin'.\n"
                "- Any of these canonical keys that do not naturally appear in the text MUST be added to content.operational_fields. They are mandatory for backend processing.\n"
            )

        return (
            "You are a legal template generator. Return ONLY valid JSON.\n"
            "The JSON must match this schema:\n"
            "{\n"
            '  "name": string,\n'
            '  "description": string|null,\n'
            '  "content": {\n'
            '    "body_md": string,\n'
            '    "fields": [\n'
            '      {"key": string, "label": string, "type": string, "required": boolean, "placeholder": string|null}\n'
            "    ],\n"
            '    "operational_fields": [\n'
            '      {"key": string, "label": string, "type": string, "required": boolean, "placeholder": string|null}\n'
            "    ],\n"
            '    "contract_date_mapping": {"start_date_field": string, "end_date_field": string} | null,\n'
            '    "version": "1.0"\n'
            "  },\n"
            '  "warnings": [string],\n'
            '  "source": {}\n'
            "}\n\n"
            "Rules:\n"
            "- Use only these field types: text, number, date, time, boolean.\n"
            "- Use type 'time' for hour-only values such as hora_inicio, hora_fin, hora_ingreso or horario_refrigerio.\n"
            "- Use type 'text' for identifiers such as DNI and RUC.\n"
            "- Use type 'text' for fields expressed in words or letters, such as monto_literal or remuneracion_en_letras.\n"
            "- Use snake_case for keys.\n"
            "- Use Jinja placeholders like {{ key }} in body_md.\n"
            "- Provide a useful placeholder example for every field and operational field. Use examples prefixed with 'Ej.' and never instructional text like 'Ingrese', 'Seleccione' or 'Indique'.\n"
            "- Respect DOCUMENT_TYPE and FORMAT_CODE as the target base format for the draft.\n"
            "- Every placeholder must exist in fields or be one of these auto variables:\n"
            "  empleador_razon_social, empleador_ruc, empleador_domicilio, empleador_descripcion,\n"
            "  empleador_objeto_social, representante_nombre, representante_dni, jurisdiccion,\n"
            "  lugar_firma, autorizacion_entidad, autorizacion_fecha, autorizacion_emitida_por,\n"
            "  empleador_email, empleador_telefono, day_sign, month_sign, year_sign.\n"
            "- If ORGANIZATION_CONTEXT is present, use it only as drafting context. Do not hardcode those values in body_md when an auto variable exists.\n"
            "- Use only the auto variables that are relevant for the contract. Do not force every available variable into the template.\n"
            "- For employer-side data that already exists as an auto variable, use the canonical auto variable name instead of creating aliases like representante_nombre_empresa or ruc_empresa.\n"
            "- Do not use filters inside placeholders.\n"
            "- Each placeholder must appear at most once across content.fields and content.operational_fields.\n"
            "- If a placeholder appears in body_md, define it ONLY in content.fields. If it is required by backend workflows but does not appear in body_md, define it ONLY in content.operational_fields.\n"
            "- Reuse one canonical key per fact. Do not invent naming variants for the same party attribute unless the contract text clearly distinguishes them as different facts.\n"
            "- Any placeholder that appears directly in body_md must be marked as required=true. Optional visible placeholders are not allowed because they break the contract text when empty.\n"
            "- Use content.operational_fields for extra form fields needed by backend workflows when they should not appear in body_md.\n"
            "- When the contract defines a validity term, duration, plazo or vigencia, expose the contract start and end as dedicated placeholders if they belong in the contract text; otherwise put them in content.operational_fields, and set content.contract_date_mapping accordingly.\n"
            "- A duration-only field such as duracion_contrato or plazo_contrato is not equivalent to start_date or end_date and must not be mapped as either boundary.\n"
            "- The fields referenced by content.contract_date_mapping must exist either in content.fields or content.operational_fields. Prefer type 'date' for those fields.\n"
            "- If the contract does not expose both dates clearly enough, set content.contract_date_mapping to null and add a warning describing the ambiguity.\n"
            "- If REFERENCE_CONTEXT is present, preserve the original contract structure as faithfully as possible. Replace variable values with placeholders, but do not freely rewrite or summarize clauses.\n"
            "- If REFERENCE_OUTLINE is present, preserve every item in clause_sequence when available, and otherwise preserve the order of structure_sequence. Do not omit structural markers that appear in the reference.\n"
            "- Preserve section titles and the closing section when they appear in the reference.\n"
            "- Do not include signature blocks, underscore signature lines, signer labels, or representative placeholders at the end of body_md. Signature rendering is handled by the backend.\n"
            "- GENERATION_MODE controls how strictly the result must follow the reference.\n"
            "- If GENERATION_MODE is strict, stay as close as possible to the original wording. Do not add new legal clauses that are absent from the reference just to make the template operational.\n"
            "- If GENERATION_MODE is adaptive, the reference is guidance, not a literal constraint. You may add a concise vigencia clause to body_md when explicit contract start and end placeholders are needed.\n"
            "- Preserve distinct placeholders from the reference unless they are clearly invalid. Do not aggressively merge or remove fields.\n"
            "- Convert reference markers written as [NOMBRE DEL CAMPO] into proper Jinja placeholders instead of leaving them literal in body_md.\n"
            "- If VALIDATION_FEEDBACK is present, correct every listed issue in this attempt.\n"
            "- Use Spanish legal language in body_md.\n"
            f"{domain_rules}\n"
            f"NAME_HINT: {name_hint}\n"
            f"DESCRIPTION_HINT: {description_hint}\n"
            f"DOCUMENT_TYPE: {document_type}\n"
            f"FORMAT_CODE: {format_code}\n"
            f"GENERATION_MODE: {generation_mode}\n"
            f"JURISDICTION: {jurisdiction}\n"
            f"INSTRUCTIONS: {instructions}\n"
            f"{organization_section}"
            f"{reference_outline_section}"
            f"{feedback_section}"
            f"{reference_section}"
        )
