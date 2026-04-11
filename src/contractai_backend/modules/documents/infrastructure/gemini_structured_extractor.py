"""Azure OpenAI-based structured metadata extraction for uploaded documents."""

import json
from collections.abc import Sequence
from typing import Any

from langchain_openai import AzureChatOpenAI

from ....modules.catalog.domain.entities import ServiceTable
from ....shared.config import settings
from ..application.dto import ExtractedDocumentData
from ..application.repositories import DocumentStructuredExtractor


class GeminiDocumentStructuredExtractor(DocumentStructuredExtractor):
    """Uses Azure OpenAI GPT to infer nullable metadata from parsed document chunks."""

    def __init__(self):
        self.llm = AzureChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL_NAME,
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            azure_deployment=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            temperature=0,
            max_retries=1,
            timeout=30,
        )

    async def extract(
        self,
        filename: str,
        chunks: Sequence[Any],
        available_services: Sequence[ServiceTable],
    ) -> ExtractedDocumentData:
        markdown = self._serialize_chunks(chunks=chunks)
        if not markdown:
            return ExtractedDocumentData()

        prompt = self._build_prompt(
            filename=filename,
            markdown=markdown,
            available_services=available_services,
        )
        response = await self.llm.ainvoke(prompt)
        payload = self._parse_json(self._coerce_content_to_text(response=response))
        return ExtractedDocumentData.model_validate(payload)

    @staticmethod
    def _serialize_chunks(chunks: Sequence[Any]) -> str:
        parts: list[str] = []
        for chunk in chunks:
            text = getattr(chunk, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

        return "\n\n".join(parts)[:20000]

    @staticmethod
    def _coerce_content_to_text(response: Any) -> str:
        raw_content: Any = response.content if hasattr(response, "content") else response
        if isinstance(raw_content, str):
            return raw_content
        if isinstance(raw_content, list):
            parts: list[str] = []
            for item in raw_content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("text") or item))
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        return str(raw_content)

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
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
            return json.loads(cleaned[start : end + 1])

    @staticmethod
    def _serialize_service_catalog(available_services: Sequence[ServiceTable]) -> str:
        if not available_services:
            return "No catalog services available for this organization. service_items must be []."

        return "\n".join(f"- id={service.id} | name={service.name}" for service in available_services if service.id is not None)

    @classmethod
    def _build_prompt(
        cls,
        filename: str,
        markdown: str,
        available_services: Sequence[ServiceTable],
    ) -> str:
        service_catalog = cls._serialize_service_catalog(available_services=available_services)

        return (
            "You extract contract metadata. Return ONLY valid JSON.\n"
            "Use null when the document does not clearly provide the value.\n"
            "Do not invent names, clients, dates, amounts or currencies.\n"
            "Do not calculate or return state.\n"
            "Allowed type values: COMPANY, LABOR, null.\n"
            "Allowed currency values: PEN, USD, EUR, null.\n"
            "If there are many dates, choose the main contract start/end dates only when explicit. Otherwise use null.\n"
            "If the title is not explicit, name must be null.\n"
            "client should be the external company/person identified as cliente, contratante, contraparte or worker/employee when applicable. If ambiguous, null.\n"
            "type should be COMPANY for corporate/commercial/company contracts and LABOR for employment or HR contracts.\n"
            "value should be the total contract amount only, not monthly or partial amounts unless the total is explicit.\n"
            "For service_items, you MUST use only service_id values from the provided organization catalog.\n"
            "Include a service item only when the mapping to a catalog service is clear AND the contract explicitly provides value, currency, start_date and end_date for that specific service.\n"
            "If any service field is missing or ambiguous, omit that item entirely.\n"
            "If no service item is fully supported by the document, return service_items as [].\n"
            "Schema:\n"
            "{\n"
            '  "name": string | null,\n'
            '  "client": string | null,\n'
            '  "type": "COMPANY" | "LABOR" | null,\n'
            '  "start_date": "YYYY-MM-DD" | null,\n'
            '  "end_date": "YYYY-MM-DD" | null,\n'
            '  "form_data": {\n'
            '    "value": number | null,\n'
            '    "currency": "PEN" | "USD" | "EUR" | null\n'
            "  },\n"
            '  "service_items": [\n'
            "    {\n"
            '      "service_id": number,\n'
            '      "description": string | null,\n'
            '      "value": number,\n'
            '      "currency": "PEN" | "USD" | "EUR",\n'
            '      "start_date": "YYYY-MM-DD",\n'
            '      "end_date": "YYYY-MM-DD"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"FILENAME: {filename}\n"
            "ORGANIZATION_SERVICE_CATALOG:\n"
            f"{service_catalog}\n\n"
            "DOCUMENT_MARKDOWN:\n"
            f"{markdown}"
        )
