"""Gemini-based template draft generator."""

import json
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from ....shared.config import settings
from ..api.schemas import GenerateTemplateDraftRequest, TemplateDraftResponse
from ..application.repositories.base_draft_generator import ITemplateDraftGenerator


class GeminiTemplateDraftGenerator(ITemplateDraftGenerator):
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL_NAME,
            api_key=settings.GEMINI_API_KEY,
            temperature=settings.MODEL_TEMPERATURE,
            max_retries=0,
        )

    async def generate(
        self,
        request: GenerateTemplateDraftRequest,
        reference_markdown: str | None = None,
    ) -> TemplateDraftResponse:
        """Genera un borrador de plantilla a partir de instrucciones y, opcionalmente, un contrato de referencia."""
        prompt = self._build_prompt(request=request, reference_markdown=reference_markdown)
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
        return TemplateDraftResponse.model_validate(payload)

    def _parse_json(self, raw: str) -> dict[str, Any]:
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

    def _build_prompt(
        self,
        request: GenerateTemplateDraftRequest,
        reference_markdown: str | None = None,
    ) -> str:
        preferred_fields = ", ".join(request.preferred_fields) if request.preferred_fields else ""
        instructions = request.instructions or ""
        name_hint = request.name or ""
        description_hint = request.description or ""
        contract_type = request.contract_type or ""
        jurisdiction = request.jurisdiction or ""

        reference_section = ""
        if reference_markdown:
            reference_section = "\nREFERENCE_DOCUMENT:\n" + reference_markdown[:12000]

        return (
            "You are a legal template generator. Return ONLY valid JSON.\n"
            "The JSON must match this schema:\n"
            "{\n"
            '  "name": string,\n'
            '  "description": string|null,\n'
            '  "content": {\n'
            '    "body_md": string,\n'
            '    "fields": [\n'
            '      {"key": string, "label": string, "type": string, "required": boolean}\n'
            "    ],\n"
            '    "version": "1.0"\n'
            "  },\n"
            '  "warnings": [string],\n'
            '  "source": {}\n'
            "}\n\n"
            "Rules:\n"
            "- Use only these field types: text, number, date, boolean.\n"
            "- Use snake_case for keys.\n"
            "- Use Jinja placeholders like {{ key }} in body_md.\n"
            "- Every placeholder must exist in fields or be one of these auto variables:\n"
            "  empleador_razon_social, empleador_ruc, empleador_domicilio, empleador_descripcion,\n"
            "  empleador_objeto_social, representante_nombre, representante_dni, jurisdiccion,\n"
            "  lugar_firma, autorizacion_entidad, autorizacion_fecha, autorizacion_emitida_por,\n"
            "  empleador_email, empleador_telefono, day_sign, month_sign, year_sign.\n"
            "- Do not use filters inside placeholders.\n"
            "- Keep structure and clauses from the reference when provided.\n"
            "- Use Spanish legal language in body_md.\n\n"
            f"NAME_HINT: {name_hint}\n"
            f"DESCRIPTION_HINT: {description_hint}\n"
            f"CONTRACT_TYPE: {contract_type}\n"
            f"JURISDICTION: {jurisdiction}\n"
            f"PREFERRED_FIELDS: {preferred_fields}\n"
            f"INSTRUCTIONS: {instructions}\n"
            f"{reference_section}"
        )
