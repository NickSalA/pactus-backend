"""GPT-based template draft generator."""

import json
import re
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from ....shared.config import settings
from ..application.dto import GenerateTemplateDraftRequest, TemplateDraftResponse, TemplateUsage
from ..application.repositories.base_draft_generator import ITemplateDraftGenerator
from ..application.services.template_placeholder_generator import TemplatePlaceholderGenerator
from ..domain.patterns import AUTO_VARIABLES
from .prompts import build_system_prompt


class GeminiTemplateDraftGenerator(ITemplateDraftGenerator):

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
        if field_issues := self._detect_raw_field_issues(payload):
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
        if placeholder and TemplatePlaceholderGenerator.should_autogenerate_placeholder(placeholder):
            issues.append(f"El campo '{key}' debe usar un placeholder de ejemplo con 'Ej.' y no texto instruccional.")
        return issues

    def _field_tokens(self, *, key: str, label: str) -> set[str]:
        """Builds normalized tokens from a field key and label."""
        normalized = re.sub(r"[^a-z0-9]+", "_", f"{key} {label}".lower()).strip("_")
        return {token for token in normalized.split("_") if token}

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

        system_instructions = build_system_prompt(
            auto_variables=AUTO_VARIABLES,
            document_type=document_type,
            has_organization=bool(organization_context),
            has_reference=bool(reference_context),
            has_outline=bool(reference_outline),
            has_feedback=bool(validation_feedback),
            generation_mode=generation_mode,
        )

        return (
            f"{system_instructions}\n"
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
