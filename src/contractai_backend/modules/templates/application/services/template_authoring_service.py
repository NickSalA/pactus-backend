"""Service for generating template drafts and previews."""

from datetime import datetime
from typing import Any

from contractai_backend.modules.documents.application.repositories import DocumentExtractor
from contractai_backend.modules.documents.domain import DocumentType

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
from .template_content_synchronizer import TemplateContentSynchronizer
from .template_placeholder_validator import TemplatePlaceholderValidator
from .template_reference_preprocessor import TemplateReferenceContext, TemplateReferencePreprocessor


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
        self.content_synchronizer = TemplateContentSynchronizer()
        self.validator = TemplatePlaceholderValidator()
        self.reference_preprocessor = TemplateReferencePreprocessor()

    async def generate_draft_from_prompt(
        self,
        request: GenerateTemplateDraftRequest,
        organization_id: int,
    ) -> TemplateDraftResponse:
        """Genera un borrador guiado por formulario."""
        organization_context = await self._build_organization_context(organization_id=organization_id)
        draft = await self.draft_generator.generate(request=request, organization_context=organization_context)
        draft.content = self.content_synchronizer.sync(draft.content)
        draft.warnings.extend(self.validator.validate(draft.content))
        return draft

    async def generate_and_save_draft_from_prompt(
        self,
        request: GenerateTemplateDraftRequest,
        organization_id: int,
    ) -> PersistedTemplateDraftResponse:
        """Genera y persiste un borrador desde formulario."""
        draft = await self.generate_draft_from_prompt(request=request, organization_id=organization_id)
        template = await self._persist_draft(
            draft=draft,
            organization_id=organization_id,
            document_type=self._resolve_requested_document_type(request=request),
        )
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
        reference_context = self.reference_preprocessor.build(extracted_pages)
        organization_context = await self._build_organization_context(organization_id=organization_id)

        draft, retries_used = await self._generate_validated_file_draft(
            request=request,
            reference_context=reference_context,
            organization_context=organization_context,
        )
        draft.source = {
            "mode": "file_reference",
            "filename": filename,
            "reference_mode": reference_context.mode,
            "section_titles": list(reference_context.section_titles),
            "reference_chars": len(reference_context.prompt_text),
            "original_chars": reference_context.original_chars,
            "clean_chars": reference_context.clean_chars,
            "clause_count": len(reference_context.clause_sequence),
            "first_clause": reference_context.clause_sequence[0] if reference_context.clause_sequence else None,
            "last_clause": reference_context.clause_sequence[-1] if reference_context.clause_sequence else None,
            "clause_sequence": list(reference_context.clause_sequence),
            "structure_count": len(reference_context.structure_sequence),
            "structure_sequence": list(reference_context.structure_sequence),
            "retries_used": retries_used,
        }
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
        template = await self._persist_draft(
            draft=draft,
            organization_id=organization_id,
            document_type=self._resolve_requested_document_type(request=request),
        )
        return PersistedTemplateDraftResponse(template=template, warnings=draft.warnings, source=draft.source, usage=draft.usage)

    async def preview_template(
        self,
        request: PreviewTemplateRequest,
        organization_id: int,
    ) -> PreviewTemplateResponse:
        """Renderiza una vista previa de la plantilla."""
        synced_content = self.content_synchronizer.sync(request.content)
        warnings = self.validator.validate(synced_content)
        org_data = await self.organization_repo.get_organization_data(organization_id=organization_id)
        payload = {
            **self._build_mock_payload(synced_content.fields),
            **org_data,
            **self._build_time_payload(),
            **request.sample_data,
        }
        markdown = await self.renderer.render(template_md=synced_content.body_md, payload=payload)
        return PreviewTemplateResponse(markdown=markdown, resolved_payload=payload, warnings=warnings)

    async def create_template(
        self,
        request: CreateTemplateRequest,
        organization_id: int,
    ) -> TemplateResponse:
        """Crea una plantilla manual en borrador."""
        synced_content = self.content_synchronizer.sync(request.content)
        self.validator.validate(synced_content)
        template = self._build_template_entity(
            organization_id=organization_id,
            name=request.name,
            description=request.description,
            document_type=request.document_type,
            content=synced_content,
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

        fields_set = request.model_fields_set

        if "content" in fields_set:
            if request.content is None:
                raise ValueError("Content cannot be null")
            synced_content = self.content_synchronizer.sync(request.content)
            self.validator.validate(synced_content)
            template.content = synced_content.model_dump(mode="python")
        if "name" in fields_set:
            if request.name is None:
                raise ValueError("Name cannot be null")
            template.name = request.name
        if "description" in fields_set:
            template.description = request.description
        if "document_type" in fields_set:
            if request.document_type is None:
                raise ValueError("Document type cannot be null")
            template.document_type = request.document_type

        updated_template = await self.template_repo.update(entity=template)
        return build_template_response(updated_template)

    async def publish_template(self, template_id: int, organization_id: int) -> TemplateResponse:
        """Publica una plantilla en borrador."""
        template = await self._get_template_or_raise(template_id=template_id, organization_id=organization_id)
        if template.state != TemplateState.DRAFT:
            raise ValueError("Solo se pueden publicar plantillas en estado DRAFT.")

        content = self.content_synchronizer.sync(TemplateContent.model_validate(template.content))
        self.validator.validate(content)
        content.version = self._resolve_publish_version(content.version)

        template.content = content.model_dump(mode="python")
        template.state = TemplateState.PUBLISHED
        published_template = await self.template_repo.update(entity=template)
        return build_template_response(published_template)

    async def _persist_draft(
        self,
        draft: TemplateDraftResponse,
        organization_id: int,
        document_type: DocumentType,
    ) -> TemplateResponse:
        """Guarda un borrador generado en la base de datos."""
        template = self._build_template_entity(
            organization_id=organization_id,
            name=draft.name,
            description=draft.description,
            document_type=document_type,
            content=draft.content,
        )
        saved_template = await self.template_repo.save(entity=template)
        return build_template_response(saved_template)

    async def _generate_validated_file_draft(
        self,
        request: GenerateTemplateDraftRequest,
        reference_context: TemplateReferenceContext,
        organization_context: dict[str, Any],
    ) -> tuple[TemplateDraftResponse, int]:
        """Genera un draft de archivo con autocorreccion estructural."""
        retry_feedback: list[str] = []
        max_attempts = 2

        for attempt in range(max_attempts):
            draft = await self.draft_generator.generate(
                request=request,
                reference_context=reference_context.prompt_text,
                reference_outline=reference_context.to_prompt_outline(),
                organization_context=organization_context,
                validation_feedback=retry_feedback or None,
            )
            draft.content = self.content_synchronizer.sync(draft.content)

            try:
                warnings = self.validator.validate(draft.content)
            except ValueError as exc:
                if attempt == max_attempts - 1:
                    raise
                retry_feedback = [str(exc)]
                continue

            reference_warnings = self.validator.validate_against_reference(
                draft.content.body_md,
                reference_context.clause_sequence,
            )
            if not reference_warnings and not reference_context.clause_sequence:
                reference_warnings = self.validator.validate_structure_against_reference(
                    draft.content.body_md,
                    reference_context.structure_sequence,
                )
            retryable_issues = [warning for warning in warnings if warning.startswith("Numeración de cláusulas")] + reference_warnings
            if not retryable_issues:
                draft.warnings.extend(warnings)
                return draft, attempt

            if attempt == max_attempts - 1:
                draft.warnings.extend(warnings)
                draft.warnings.extend(reference_warnings)
                return draft, attempt

            retry_feedback = retryable_issues

        raise ValueError("No se pudo generar un borrador valido desde el archivo de referencia.")

    async def _get_template_or_raise(self, template_id: int, organization_id: int) -> TemplateTable:
        """Carga una plantilla o falla si no existe."""
        template = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        if template is None:
            raise ValueError("Plantilla no encontrada")
        return template

    def _resolve_publish_version(self, version: str | None) -> str:
        """Normaliza la version al momento de publicar."""
        normalized_version = (version or "").strip()
        return normalized_version or "1.0"

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
        document_type: DocumentType,
        content: TemplateContent,
    ) -> TemplateTable:
        """Crea la entidad base de plantilla."""
        return TemplateTable(
            organization_id=organization_id,
            name=name,
            description=description,
            document_type=document_type,
            content=content.model_dump(mode="python"),
            state=TemplateState.DRAFT,
        )

    def _resolve_requested_document_type(self, request: GenerateTemplateDraftRequest) -> DocumentType:
        """Resuelve el tipo documental de un draft, manteniendo compatibilidad con requests antiguos."""
        if request.document_type is not None:
            return request.document_type

        hint = " ".join(
            value.strip().lower()
            for value in [request.contract_type, request.name, request.description, request.instructions]
            if isinstance(value, str) and value.strip()
        )

        company_markers = (
            "management",
            "gerencia",
            "gerenc",
            "hotel",
            "empresa",
            "comercial",
            "servicio",
            "cliente",
            "b2b",
        )
        if any(marker in hint for marker in company_markers):
            return DocumentType.COMPANY

        return DocumentType.LABOR

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
