"""Service for generating template drafts and previews."""

from datetime import datetime
from typing import Any

from contractai_backend.modules.documents.application.repositories import DocumentExtractor

from ...api.schemas import (
    CreateTemplateRequest,
    GenerateTemplateDraftRequest,
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    TemplateDraftResponse,
)
from ...domain.entities import TemplateField, TemplateTable
from ..repositories import IOrganizationRepository, ITemplateRenderer, ITemplateRepository
from ..repositories.base_draft_generator import ITemplateDraftGenerator
from .template_placeholder_validator import TemplatePlaceholderValidator


class TemplateAuthoringService:
    def __init__(
        self,
        template_repo: ITemplateRepository,
        organization_repo: IOrganizationRepository,
        renderer: ITemplateRenderer,
        extractor: DocumentExtractor,
        draft_generator: ITemplateDraftGenerator,
    ):
        self.template_repo = template_repo
        self.organization_repo = organization_repo
        self.renderer = renderer
        self.extractor = extractor
        self.draft_generator = draft_generator
        self.validator = TemplatePlaceholderValidator()

    async def generate_draft_from_prompt(
        self,
        request: GenerateTemplateDraftRequest,
        organization_id: int,
    ) -> TemplateDraftResponse:
        draft = await self.draft_generator.generate(request=request)
        draft.warnings.extend(self.validator.validate(draft.content))
        return draft

    async def generate_draft_from_file(
        self,
        request: GenerateTemplateDraftRequest,
        file_content: bytes,
        filename: str,
        organization_id: int,
    ) -> TemplateDraftResponse:
        extracted_pages = await self.extractor.extract(file=file_content, filename=filename)
        reference_markdown = "\n\n".join(page.text for page in extracted_pages if getattr(page, "text", "").strip())

        draft = await self.draft_generator.generate(
            request=request,
            reference_markdown=reference_markdown,
        )
        draft.source = {
            "mode": "file_reference",
            "filename": filename,
        }
        draft.warnings.extend(self.validator.validate(draft.content))
        return draft

    async def preview_template(
        self,
        request: PreviewTemplateRequest,
        organization_id: int,
    ) -> PreviewTemplateResponse:
        warnings = self.validator.validate(request.content)
        org_data = await self.organization_repo.get_organization_data(organization_id=organization_id)
        payload = {
            **self._build_mock_payload(request.content.fields),
            **org_data,
            **self._build_time_payload(),
            **request.sample_data,
        }
        markdown = await self.renderer.render(template_md=request.content.body_md, payload=payload)
        return PreviewTemplateResponse(markdown=markdown, resolved_payload=payload, warnings=warnings)

    async def create_template(
        self,
        request: CreateTemplateRequest,
        organization_id: int,
    ) -> TemplateTable:
        self.validator.validate(request.content)
        template = TemplateTable(
            organization_id=organization_id,
            name=request.name,
            description=request.description,
            content=request.content.model_dump(mode="python"),
        )
        return await self.template_repo.save(entity=template)

    def _build_time_payload(self) -> dict[str, int | str]:
        now = datetime.now()
        months = [
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ]
        return {
            "day_sign": now.day,
            "month_sign": months[now.month - 1],
            "year_sign": now.year,
        }

    def _build_mock_payload(self, fields: list[TemplateField]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field in fields:
            payload[field.key] = self._mock_value(field)
        return payload

    def _mock_value(self, field: TemplateField) -> Any:
        if field.type == "date":
            return "2026-01-01"
        if field.type == "number":
            return 1000
        if field.type == "boolean":
            return True
        return field.label
