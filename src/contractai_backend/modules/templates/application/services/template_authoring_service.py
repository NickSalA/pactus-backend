"""Service for generating template drafts and previews."""

from datetime import datetime
from typing import Any

from contractai_backend.modules.documents.application.repositories import DocumentExtractor

from ...api.schemas import (
    CreateTemplateRequest,
    GenerateTemplateDraftRequest,
    PersistedTemplateDraftResponse,
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    TemplateDraftResponse,
    TemplateResponse,
    UpdateTemplateRequest,
    build_template_response,
)
from ...domain.entities import TemplateContent, TemplateField, TemplateTable
from ...domain.value_objs import TemplateState
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
        """Stores dependencies for template authoring."""
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
        """Genera un borrador guiado por formulario."""
        organization_context = await self._build_organization_context(organization_id=organization_id)
        draft = await self.draft_generator.generate(request=request, organization_context=organization_context)
        draft.warnings.extend(self.validator.validate(draft.content))
        return draft

    async def generate_and_save_draft_from_prompt(
        self,
        request: GenerateTemplateDraftRequest,
        organization_id: int,
    ) -> PersistedTemplateDraftResponse:
        """Genera y persiste un borrador desde formulario."""
        draft = await self.generate_draft_from_prompt(request=request, organization_id=organization_id)
        template = await self._persist_draft(draft=draft, organization_id=organization_id)
        return PersistedTemplateDraftResponse(template=template, warnings=draft.warnings, source=draft.source, usage=draft.usage)

    async def generate_draft_from_file(
        self,
        request: GenerateTemplateDraftRequest,
        file_content: bytes,
        filename: str,
        organization_id: int,
    ) -> TemplateDraftResponse:
        """Genera un borrador a partir de un archivo."""
        extracted_pages = await self.extractor.extract(file=file_content, filename=filename)
        reference_markdown = "\n\n".join(page.text for page in extracted_pages if getattr(page, "text", "").strip())
        organization_context = await self._build_organization_context(organization_id=organization_id)

        draft = await self.draft_generator.generate(
            request=request,
            reference_markdown=reference_markdown,
            organization_context=organization_context,
        )
        draft.source = {
            "mode": "file_reference",
            "filename": filename,
        }
        draft.warnings.extend(self.validator.validate(draft.content))
        return draft

    async def generate_and_save_draft_from_file(
        self,
        request: GenerateTemplateDraftRequest,
        file_content: bytes,
        filename: str,
        organization_id: int,
    ) -> PersistedTemplateDraftResponse:
        """Genera y persiste un borrador desde archivo."""
        draft = await self.generate_draft_from_file(
            request=request,
            file_content=file_content,
            filename=filename,
            organization_id=organization_id,
        )
        template = await self._persist_draft(draft=draft, organization_id=organization_id)
        return PersistedTemplateDraftResponse(template=template, warnings=draft.warnings, source=draft.source, usage=draft.usage)

    async def preview_template(
        self,
        request: PreviewTemplateRequest,
        organization_id: int,
    ) -> PreviewTemplateResponse:
        """Renderiza una vista previa de la plantilla."""
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
    ) -> TemplateResponse:
        """Crea una plantilla manual en borrador."""
        self.validator.validate(request.content)
        template = self._build_template_entity(
            organization_id=organization_id,
            name=request.name,
            description=request.description,
            content=request.content,
        )
        saved_template = await self.template_repo.save(entity=template)
        return build_template_response(saved_template)

    async def update_template(
        self,
        template_id: int,
        request: UpdateTemplateRequest,
        organization_id: int,
    ) -> TemplateResponse:
        """Actualiza una plantilla en borrador."""
        template = await self._get_template_or_raise(template_id=template_id, organization_id=organization_id)
        if template.state != TemplateState.DRAFT:
            raise ValueError("Solo se pueden editar plantillas en estado DRAFT.")

        if request.content is not None:
            self.validator.validate(request.content)
            template.content = request.content.model_dump(mode="python")
        if request.name is not None:
            template.name = request.name
        if request.description is not None:
            template.description = request.description

        updated_template = await self.template_repo.update(entity=template)
        return build_template_response(updated_template)

    async def _persist_draft(self, draft: TemplateDraftResponse, organization_id: int) -> TemplateResponse:
        """Guarda un borrador generado en la base de datos."""
        template = self._build_template_entity(
            organization_id=organization_id,
            name=draft.name,
            description=draft.description,
            content=draft.content,
        )
        saved_template = await self.template_repo.save(entity=template)
        return build_template_response(saved_template)

    async def _get_template_or_raise(self, template_id: int, organization_id: int) -> TemplateTable:
        """Carga una plantilla o falla si no existe."""
        template = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        if template is None:
            raise ValueError("Plantilla no encontrada")
        return template

    async def _build_organization_context(self, organization_id: int) -> dict[str, Any]:
        """Construye contexto util para la generacion."""
        org_data = await self.organization_repo.get_organization_data(organization_id=organization_id)
        organization_profile = {
            key: value
            for key, value in {
                "empleador_razon_social": org_data.get("empleador_razon_social"),
                "empleador_descripcion": org_data.get("empleador_descripcion"),
                "empleador_objeto_social": org_data.get("empleador_objeto_social"),
                "jurisdiccion": org_data.get("jurisdiccion"),
                "lugar_firma": org_data.get("lugar_firma"),
            }.items()
            if value not in (None, "")
        }
        available_auto_variables = sorted(key for key, value in org_data.items() if key in self.validator.AUTO_VARIABLES and value not in (None, ""))
        return {
            "organization_profile": organization_profile,
            "available_auto_variables": available_auto_variables,
        }

    def _build_template_entity(
        self,
        organization_id: int,
        name: str,
        description: str | None,
        content: TemplateContent,
    ) -> TemplateTable:
        """Crea la entidad base de plantilla."""
        return TemplateTable(
            organization_id=organization_id,
            name=name,
            description=description,
            content=content.model_dump(mode="python"),
            state=TemplateState.DRAFT,
        )

    def _build_time_payload(self) -> dict[str, int | str]:
        """Genera variables automaticas de fecha."""
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
        """Genera datos mock para una preview."""
        payload: dict[str, Any] = {}
        for field in fields:
            payload[field.key] = self._mock_value(field)
        return payload

    def _mock_value(self, field: TemplateField) -> Any:
        """Devuelve un valor mock por tipo de campo."""
        if field.type == "date":
            return "2026-01-01"
        if field.type == "number":
            return 1000
        if field.type == "boolean":
            return True
        return field.label
