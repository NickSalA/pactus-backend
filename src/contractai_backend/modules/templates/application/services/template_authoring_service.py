"""Service for generating, validating and managing templates."""

from datetime import datetime
import re
import unicodedata
from typing import Any

from contractai_backend.core.exceptions.base import AppError, ForbiddenError, NotFoundError, ValidationError
from contractai_backend.modules.documents.application.repositories import DocumentExtractor
from contractai_backend.modules.documents.domain import DocumentType
from contractai_backend.modules.documents.domain.access_policy import can_write_document_type
from contractai_backend.modules.users.domain.value_objs import UserRole

from ...api.schemas import (
    CreateTemplateRequest,
    GenerateTemplateDraftRequest,
    PersistedTemplateDraftResponse,
    PreviewTemplateRequest,
    PreviewTemplateResponse,
    TemplateDraftResponse,
    TemplateFormatResponse,
    TemplateResponse,
    UpdateTemplateRequest,
    build_template_response,
)
from ...domain.entities import TemplateContent, TemplateField, TemplateTable
from ...domain.formats import is_valid_template_format, list_template_formats
from ...domain.value_objs import TemplateState
from ..repositories import IOrganizationRepository, ITemplateRenderer, ITemplateRepository
from ..repositories.base_draft_generator import ITemplateDraftGenerator
from .template_content_synchronizer import TemplateContentSynchronizer
from .template_placeholder_validator import TemplatePlaceholderValidator
from .template_reference_preprocessor import TemplateReferenceContext, TemplateReferencePreprocessor

ROLE_LOCKED_DOCUMENT_TYPES: dict[UserRole, DocumentType] = {
    UserRole.HR: DocumentType.LABOR,
    UserRole.MANAGER: DocumentType.COMPANY,
}


class TemplateAuthoringService:
    """Coordinates template authoring flows and access control."""

    LABOR_CLASSIFIER_PATTERNS = (
        r"\btrabajador(?:es)?\b",
        r"\bemplead(?:o|a|os|as)\b",
        r"\bempleador\b",
        r"\bremuneraci[oó]n\b",
        r"\bjornada\b",
        r"\bvacaciones\b",
        r"\bperiodo de prueba\b",
        r"\bplanilla\b",
        r"\bsubordinaci[oó]n\b",
        r"\bcontrato de trabajo\b",
    )
    COMPANY_CLASSIFIER_PATTERNS = (
        r"\bempresa(?:s)?\b",
        r"\bcliente(?:s)?\b",
        r"\bproveedor(?:es)?\b",
        r"\bmanagement\b",
        r"\bgerenc(?:ia|iamiento|ial)\b",
        r"\bservicio(?:s)?\b",
        r"\bpersona jur[ií]dica\b",
        r"\bsociedad an[oó]nima\b",
        r"\br\.?u\.?c\.?\b",
        r"\bcontrato comercial\b",
    )

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

    async def list_available_formats(
        self,
        user_role: UserRole,
        requested_document_type: DocumentType | None = None,
    ) -> list[TemplateFormatResponse]:
        """Lists the template formats available to the current role."""
        if user_role == UserRole.WORKER:
            raise ForbiddenError("No tiene permisos para gestionar plantillas")

        if user_role == UserRole.ADMIN:
            document_types = [requested_document_type] if requested_document_type is not None else list(DocumentType)
        else:
            effective_document_type = self._resolve_effective_document_type(
                user_role=user_role,
                requested_document_type=requested_document_type,
            )
            document_types = [effective_document_type]

        formats: list[TemplateFormatResponse] = []
        for document_type in document_types:
            for definition in list_template_formats(document_type=document_type):
                formats.append(
                    TemplateFormatResponse(
                        document_type=definition.document_type,
                        format_code=definition.format_code,
                        label=definition.label,
                    )
                )
        return formats

    async def generate_draft_from_prompt(
        self,
        request: GenerateTemplateDraftRequest,
        organization_id: int,
        user_role: UserRole,
    ) -> tuple[TemplateDraftResponse, DocumentType]:
        """Generates a draft from structured instructions."""
        document_type = self._resolve_effective_document_type(user_role=user_role, requested_document_type=request.document_type)
        self._validate_format_code(document_type=document_type, format_code=request.format_code)
        resolved_request = request.model_copy(update={"document_type": document_type})

        organization_context = await self._build_organization_context(organization_id=organization_id)
        draft = await self.draft_generator.generate(request=resolved_request, organization_context=organization_context)
        draft.content = self.content_synchronizer.sync(draft.content)
        draft.warnings.extend(self.validator.validate(draft.content))
        return draft, document_type

    async def generate_and_save_draft_from_prompt(
        self,
        request: GenerateTemplateDraftRequest,
        organization_id: int,
        user_role: UserRole,
    ) -> PersistedTemplateDraftResponse:
        """Generates and persists a draft from prompt data."""
        draft, document_type = await self.generate_draft_from_prompt(
            request=request,
            organization_id=organization_id,
            user_role=user_role,
        )
        template = await self._persist_draft(
            draft=draft,
            organization_id=organization_id,
            document_type=document_type,
            format_code=request.format_code,
        )
        return PersistedTemplateDraftResponse(template=template, warnings=draft.warnings, source=draft.source, usage=draft.usage)

    async def generate_draft_from_file(
        self,
        request: GenerateTemplateDraftRequest,
        file_content: bytes,
        filename: str,
        organization_id: int,
        user_role: UserRole,
    ) -> tuple[TemplateDraftResponse, DocumentType]:
        """Generates a draft from a reference file."""
        document_type = self._resolve_effective_document_type(user_role=user_role, requested_document_type=request.document_type)
        self._validate_format_code(document_type=document_type, format_code=request.format_code)
        resolved_request = request.model_copy(update={"document_type": document_type})

        extracted_pages = await self.extractor.extract(file=file_content, filename=filename)
        reference_context = self.reference_preprocessor.build(extracted_pages)
        self._validate_reference_document_type(reference_context=reference_context, expected_document_type=document_type)

        organization_context = await self._build_organization_context(organization_id=organization_id)
        draft, retries_used = await self._generate_validated_file_draft(
            request=resolved_request,
            reference_context=reference_context,
            organization_context=organization_context,
        )
        draft.source = {
            "mode": "file_reference",
            "filename": filename,
            "reference_mode": reference_context.mode,
            "detected_document_type": document_type.value,
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
        return draft, document_type

    async def generate_and_save_draft_from_file(
        self,
        request: GenerateTemplateDraftRequest,
        file_content: bytes,
        filename: str,
        organization_id: int,
        user_role: UserRole,
    ) -> PersistedTemplateDraftResponse:
        """Generates and persists a draft from a reference file."""
        draft, document_type = await self.generate_draft_from_file(
            request=request,
            file_content=file_content,
            filename=filename,
            organization_id=organization_id,
            user_role=user_role,
        )
        template = await self._persist_draft(
            draft=draft,
            organization_id=organization_id,
            document_type=document_type,
            format_code=request.format_code,
        )
        return PersistedTemplateDraftResponse(template=template, warnings=draft.warnings, source=draft.source, usage=draft.usage)

    async def preview_template(
        self,
        request: PreviewTemplateRequest,
        organization_id: int,
        user_role: UserRole,
    ) -> PreviewTemplateResponse:
        """Renders a template preview for the current role."""
        document_type = self._resolve_effective_document_type(user_role=user_role, requested_document_type=request.document_type)
        self._validate_format_code(document_type=document_type, format_code=request.format_code)

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
        user_role: UserRole,
    ) -> TemplateResponse:
        """Creates a manual draft template."""
        document_type = self._resolve_effective_document_type(user_role=user_role, requested_document_type=request.document_type)
        self._validate_format_code(document_type=document_type, format_code=request.format_code)

        synced_content = self.content_synchronizer.sync(request.content)
        self.validator.validate(synced_content)
        template = self._build_template_entity(
            organization_id=organization_id,
            name=request.name,
            description=request.description,
            document_type=document_type,
            format_code=request.format_code,
            content=synced_content,
        )
        saved_template = await self.template_repo.save(entity=template)
        return build_template_response(saved_template)

    async def update_template(
        self,
        template_id: int,
        request: UpdateTemplateRequest,
        organization_id: int,
        user_role: UserRole,
    ) -> TemplateResponse:
        """Updates a draft template without changing its base format."""
        template = await self._get_template_or_raise(template_id=template_id, organization_id=organization_id)
        self._ensure_can_author_document_type(user_role=user_role, document_type=template.document_type)
        if template.state != TemplateState.DRAFT:
            raise ValidationError("Solo se pueden editar plantillas en estado DRAFT.")

        fields_set = request.model_fields_set

        if "content" in fields_set:
            if request.content is None:
                raise ValidationError("Content cannot be null")
            synced_content = self.content_synchronizer.sync(request.content)
            self.validator.validate(synced_content)
            template.content = synced_content.model_dump(mode="python")
        if "name" in fields_set:
            if request.name is None:
                raise ValidationError("Name cannot be null")
            template.name = request.name
        if "description" in fields_set:
            template.description = request.description

        updated_template = await self.template_repo.update(entity=template)
        return build_template_response(updated_template)

    async def publish_template(
        self,
        template_id: int,
        organization_id: int,
        user_role: UserRole,
    ) -> TemplateResponse:
        """Publishes a draft template."""
        template = await self._get_template_or_raise(template_id=template_id, organization_id=organization_id)
        self._ensure_can_author_document_type(user_role=user_role, document_type=template.document_type)
        if template.state != TemplateState.DRAFT:
            raise ValidationError("Solo se pueden publicar plantillas en estado DRAFT.")
        if not template.format_code:
            raise ValidationError("La plantilla debe tener format_code antes de publicarse.")
        self._validate_format_code(document_type=template.document_type, format_code=template.format_code)

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
        format_code: str,
    ) -> TemplateResponse:
        """Persists a generated draft template."""
        template = self._build_template_entity(
            organization_id=organization_id,
            name=draft.name,
            description=draft.description,
            document_type=document_type,
            format_code=format_code,
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
        """Generates a file-based draft with one structural retry."""
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

        raise ValidationError("No se pudo generar un borrador valido desde el archivo de referencia.")

    async def _get_template_or_raise(self, template_id: int, organization_id: int) -> TemplateTable:
        """Loads one template or raises a not found error."""
        template = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        if template is None:
            raise NotFoundError("Plantilla no encontrada")
        return template

    def _resolve_publish_version(self, version: str | None) -> str:
        """Normalizes the version on publish."""
        normalized_version = (version or "").strip()
        return normalized_version or "1.0"

    async def _build_organization_context(self, organization_id: int) -> dict[str, Any]:
        """Builds organization context for draft generation."""
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
        format_code: str,
        content: TemplateContent,
    ) -> TemplateTable:
        """Builds the base template entity."""
        return TemplateTable(
            organization_id=organization_id,
            name=name,
            description=description,
            document_type=document_type,
            format_code=format_code,
            content=content.model_dump(mode="python"),
            state=TemplateState.DRAFT,
        )

    def _resolve_effective_document_type(
        self,
        user_role: UserRole,
        requested_document_type: DocumentType | None,
    ) -> DocumentType:
        """Resolves the effective document type for authoring operations."""
        if user_role == UserRole.ADMIN:
            if requested_document_type is None:
                raise ValidationError("document_type es obligatorio para usuarios ADMIN.")
            return requested_document_type

        locked_document_type = ROLE_LOCKED_DOCUMENT_TYPES.get(user_role)
        if locked_document_type is None:
            raise ForbiddenError("No tiene permisos para gestionar plantillas")

        if requested_document_type is not None and requested_document_type != locked_document_type:
            raise ForbiddenError(f"No tiene permisos para crear plantillas de tipo {requested_document_type.value}.")

        return locked_document_type

    def _ensure_can_author_document_type(self, user_role: UserRole, document_type: DocumentType) -> None:
        """Checks whether the current role can author templates for the type."""
        if not can_write_document_type(user_role=user_role, document_type=document_type):
            raise ForbiddenError(f"No tiene permisos para gestionar plantillas de tipo {document_type.value}.")

    def _validate_format_code(self, document_type: DocumentType, format_code: str) -> None:
        """Validates that the format belongs to the selected base type."""
        if not is_valid_template_format(document_type=document_type, format_code=format_code):
            raise ValidationError(f"format_code '{format_code}' no es válido para document_type '{document_type.value}'.")

    def _validate_reference_document_type(
        self,
        reference_context: TemplateReferenceContext,
        expected_document_type: DocumentType,
    ) -> None:
        """Validates that the uploaded file matches the expected base type."""
        detected_document_type = self._classify_reference_document_type(reference_context.clean_text)
        if detected_document_type is None:
            raise AppError("No se pudo determinar si el archivo corresponde a COMPANY o LABOR.", status_code=422)
        if detected_document_type != expected_document_type:
            raise AppError(
                f"El archivo no corresponde a una plantilla de tipo {expected_document_type.value}.",
                status_code=422,
            )

    def _classify_reference_document_type(self, clean_text: str) -> DocumentType | None:
        """Classifies a reference document as COMPANY or LABOR using heuristics."""
        normalized_text = self._normalize_reference_text(clean_text)
        labor_score = sum(1 for pattern in self.LABOR_CLASSIFIER_PATTERNS if re.search(pattern, normalized_text))
        company_score = sum(1 for pattern in self.COMPANY_CLASSIFIER_PATTERNS if re.search(pattern, normalized_text))

        if labor_score == 0 and company_score == 0:
            return None
        if company_score >= labor_score + 2:
            return DocumentType.COMPANY
        if labor_score >= company_score + 2:
            return DocumentType.LABOR
        return None

    def _normalize_reference_text(self, value: str) -> str:
        """Normalizes extracted text for heuristic matching."""
        normalized = unicodedata.normalize("NFD", value)
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return re.sub(r"\s+", " ", normalized).strip().lower()

    def _build_time_payload(self) -> dict[str, int | str]:
        """Builds automatic date placeholders."""
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
        """Builds mock payload values for preview."""
        payload: dict[str, Any] = {}
        for field in fields:
            payload[field.key] = self._mock_value(field)
        return payload

    def _mock_value(self, field: TemplateField) -> Any:
        """Builds a mock value by field type."""
        if field.type == "date":
            return "2026-01-01"
        if field.type == "number":
            return 1000
        if field.type == "boolean":
            return True
        return field.label
