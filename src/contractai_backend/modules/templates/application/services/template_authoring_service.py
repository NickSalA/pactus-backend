"""Service for generating, validating and managing templates."""

import re
import unicodedata
from datetime import datetime
from typing import Any

from .....core.exceptions.base import AppError, ForbiddenError, NotFoundError, ValidationError
from ....documents.application.repositories import DocumentExtractor
from ....documents.domain import DocumentType
from ....documents.domain.access_policy import can_write_document_type
from ....users.domain.value_objs import UserRole
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
from ...domain.entities import TemplateContent, TemplateField, TemplateFormatTable, TemplateTable
from ...domain.value_objs import TemplateGenerationMode, TemplateState
from ..repositories import IOrganizationRepository, ITemplateFormatRepository, ITemplateRenderer, ITemplateRepository
from ..repositories.base_draft_generator import ITemplateDraftGenerator
from .rendered_contract_formatter import RenderedContractFormatter
from .template_content_synchronizer import TemplateContentSynchronizer
from .template_placeholder_validator import TemplatePlaceholderValidator
from .template_reference_preprocessor import TemplateReferenceContext, TemplateReferencePreprocessor
from .template_runtime_payloads import build_signature_time_payload

ROLE_LOCKED_DOCUMENT_TYPES: dict[UserRole, DocumentType] = {
    UserRole.HR: DocumentType.LABOR,
    UserRole.MANAGER: DocumentType.COMPANY,
}


class TemplateAuthoringService:
    """Coordinates template authoring flows and access control."""

    EXPLICIT_CONTRACT_DATES_REQUIRED_MESSAGE = (
        "La plantilla de referencia no expone fechas de inicio y fin del contrato de forma explícita. "
        "Usa generation_mode='adaptive' para permitir que la IA las complete."
    )
    STALE_AI_WARNING_PATTERNS = (
        re.compile(r"^El campo '.*' no est[aá] siendo utilizado en el cuerpo del documento\.?$", re.IGNORECASE),
        re.compile(r"^Campos definidos pero no usados:", re.IGNORECASE),
    )

    CONTRACT_CLOSING_PATTERNS = (
        r"(?im)^en fe de lo cual\b",
        r"(?im)^en se[nñ]al de conformidad\b",
        r"(?im)^para constancia\b",
        r"(?im)^firman\b",
        r"(?im)^suscriben\b",
    )

    LABOR_CLASSIFIER_PATTERNS = (
        (r"\btrabajador(?:es)?\b", 2),
        (r"\bemplead(?:o|a|os|as)\b", 2),
        (r"\bempleador\b", 2),
        (r"\bremuneraci[oó]n\b", 2),
        (r"\bjornada\b", 2),
        (r"\bvacaciones\b", 2),
        (r"\bperiodo de prueba\b", 3),
        (r"\bplanilla\b", 3),
        (r"\bsubordinaci[oó]n\b", 3),
        (r"\bsujeto a modalidad\b", 4),
        (r"\bcontrato de trabajo\b", 4),
        (r"\bdecreto legislativo\s*(?:n[°oº]?\s*)?728\b", 4),
        (r"\bley de productividad y competitividad laboral\b", 4),
    )
    COMPANY_CLASSIFIER_PATTERNS = (
        (r"\bempresa(?:s)?\b", 1),
        (r"\bcliente(?:s)?\b", 2),
        (r"\bproveedor(?:es)?\b", 2),
        (r"\bmanagement\b", 4),
        (r"\bgerenc(?:ia|iamiento|ial)\b", 4),
        (r"\bservicio(?:s)?\b", 1),
        (r"\bpersona jur[ií]dica\b", 2),
        (r"\bsociedad an[oó]nima\b", 2),
        (r"\br\.?u\.?c\.?\b", 1),
        (r"\bcontrato comercial\b", 3),
    )

    def __init__(
        self,
        template_repo: ITemplateRepository,
        template_format_repo: ITemplateFormatRepository,
        organization_repo: IOrganizationRepository,
        renderer: ITemplateRenderer,
        extractor: DocumentExtractor,
        draft_generator: ITemplateDraftGenerator,
    ):
        """Stores dependencies for template authoring."""
        self.template_repo = template_repo
        self.template_format_repo = template_format_repo
        self.organization_repo = organization_repo
        self.renderer = renderer
        self.extractor = extractor
        self.draft_generator = draft_generator
        self.content_synchronizer = TemplateContentSynchronizer()
        self.validator = TemplatePlaceholderValidator()
        self.reference_preprocessor = TemplateReferencePreprocessor()
        self.rendered_contract_formatter = RenderedContractFormatter()

    async def list_available_formats(
        self,
        user_role: UserRole,
        requested_document_type: DocumentType | None = None,
    ) -> list[TemplateFormatResponse]:
        """Lists the template formats available to the current role."""
        if user_role == UserRole.WORKER:
            raise ForbiddenError("No tiene permisos para gestionar plantillas")

        effective_document_type = None
        if user_role != UserRole.ADMIN:
            effective_document_type = self._resolve_effective_document_type(
                user_role=user_role,
                requested_document_type=requested_document_type,
            )
        elif requested_document_type is not None:
            effective_document_type = requested_document_type

        formats = await self.template_format_repo.list_active(document_type=effective_document_type)
        return [self._build_template_format_response(template_format) for template_format in formats]

    async def generate_draft_from_prompt(
        self,
        request: GenerateTemplateDraftRequest,
        organization_id: int,
        user_role: UserRole,
    ) -> tuple[TemplateDraftResponse, DocumentType]:
        """Generates a draft from structured instructions."""
        document_type = self._resolve_effective_document_type(user_role=user_role, requested_document_type=request.document_type)
        template_format = await self._get_template_format_or_raise(document_type=document_type, format_code=request.format_code)
        resolved_request = self._apply_format_defaults(
            request=request,
            document_type=document_type,
            template_format=template_format,
        )

        organization_context = await self._build_organization_context(organization_id=organization_id)
        draft, retries_used = await self._generate_validated_prompt_draft(
            request=resolved_request,
            document_type=document_type,
            organization_context=organization_context,
        )
        draft.source = {
            **draft.source,
            "mode": draft.source.get("mode", "prompt"),
            "generation_mode": resolved_request.generation_mode.value,
            "retries_used": retries_used,
        }
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
        template_format = await self._get_template_format_or_raise(document_type=document_type, format_code=request.format_code)
        resolved_request = self._apply_format_defaults(
            request=request,
            document_type=document_type,
            template_format=template_format,
        )

        extracted_pages = await self.extractor.extract(file=file_content, filename=filename)
        reference_context = self.reference_preprocessor.build(extracted_pages)
        self._validate_reference_document_type(reference_context=reference_context, expected_document_type=document_type)

        organization_context = await self._build_organization_context(organization_id=organization_id)
        draft, retries_used = await self._generate_validated_file_draft(
            request=resolved_request,
            document_type=document_type,
            reference_context=reference_context,
            organization_context=organization_context,
        )
        draft.source = {
            "mode": "file_reference",
            "filename": filename,
            "generation_mode": resolved_request.generation_mode.value,
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
        await self._get_template_format_or_raise(document_type=document_type, format_code=request.format_code)

        synced_content = self.content_synchronizer.sync(request.content)
        warnings = self.validator.validate(synced_content, document_type=document_type)
        org_data = await self.organization_repo.get_organization_data(organization_id=organization_id)
        payload = {
            **self._build_mock_payload(synced_content.fields + synced_content.operational_fields),
            **org_data,
            **self._build_time_payload(),
            **request.sample_data,
        }
        markdown = await self.renderer.render(template_md=synced_content.body_md, payload=payload)
        markdown = self.rendered_contract_formatter.format(markdown, document_type=document_type, payload=payload)
        return PreviewTemplateResponse(markdown=markdown, resolved_payload=payload, warnings=warnings)

    async def create_template(
        self,
        request: CreateTemplateRequest,
        organization_id: int,
        user_role: UserRole,
    ) -> TemplateResponse:
        """Creates a manual draft template."""
        document_type = self._resolve_effective_document_type(user_role=user_role, requested_document_type=request.document_type)
        template_format = await self._get_template_format_or_raise(document_type=document_type, format_code=request.format_code)

        synced_content = self.content_synchronizer.sync(request.content)
        self.validator.validate(synced_content, document_type=document_type)
        template = self._build_template_entity(
            organization_id=organization_id,
            name=request.name or self._resolve_template_default_name(template_format),
            description=request.description if request.description is not None else template_format.default_description,
            document_type=document_type,
            template_format_id=template_format.id,
            content=synced_content,
        )
        saved_template = await self.template_repo.save(entity=template)
        return build_template_response(saved_template, template_format=template_format)

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
            self.validator.validate(synced_content, document_type=template.document_type)
            template.content = synced_content.model_dump(mode="python")
        if "name" in fields_set:
            if request.name is None:
                raise ValidationError("Name cannot be null")
            template.name = request.name
        if "description" in fields_set:
            template.description = request.description

        updated_template = await self.template_repo.update(entity=template)
        template_format = await self._get_template_format_by_id(template.template_format_id)
        return build_template_response(updated_template, template_format=template_format)

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
        template_format = await self._get_template_format_by_id(template.template_format_id)
        if template_format is None:
            raise ValidationError("La plantilla debe tener un formato válido antes de publicarse.")
        await self._get_template_format_or_raise(document_type=template.document_type, format_code=template_format.format_code)

        content = self.content_synchronizer.sync(TemplateContent.model_validate(template.content))
        self.validator.validate(
            content,
            document_type=template.document_type,
            require_contract_date_mapping=template.document_type == DocumentType.COMPANY,
        )
        content.version = self._resolve_publish_version(content.version)

        template.content = content.model_dump(mode="python")
        template.state = TemplateState.PUBLISHED
        published_template = await self.template_repo.publish(entity=template)
        return build_template_response(published_template, template_format=template_format)

    async def archive_template(
        self,
        template_id: int,
        organization_id: int,
        user_role: UserRole,
    ) -> TemplateResponse:
        """Archives a template that should no longer be used."""
        template = await self._get_template_or_raise(template_id=template_id, organization_id=organization_id)
        self._ensure_can_author_document_type(user_role=user_role, document_type=template.document_type)
        if template.state == TemplateState.ARCHIVED:
            raise ValidationError("La plantilla ya se encuentra archivada.")

        template.state = TemplateState.ARCHIVED
        archived_template = await self.template_repo.update(entity=template)
        template_format = await self._get_template_format_by_id(template.template_format_id)
        return build_template_response(archived_template, template_format=template_format)

    async def _persist_draft(
        self,
        draft: TemplateDraftResponse,
        organization_id: int,
        document_type: DocumentType,
        format_code: str,
    ) -> TemplateResponse:
        """Persists a generated draft template."""
        template_format = await self._get_template_format_or_raise(document_type=document_type, format_code=format_code)
        template = self._build_template_entity(
            organization_id=organization_id,
            name=draft.name,
            description=draft.description,
            document_type=document_type,
            template_format_id=template_format.id,
            content=draft.content,
        )
        saved_template = await self.template_repo.save(entity=template)
        return build_template_response(saved_template, template_format=template_format)

    async def _generate_validated_file_draft(
        self,
        request: GenerateTemplateDraftRequest,
        *,
        document_type: DocumentType,
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
            try:
                preparation_warnings, backend_warnings = self._prepare_and_validate_generated_draft(
                    draft,
                    document_type=document_type,
                    generation_mode=request.generation_mode,
                )
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
            retryable_issues = (
                [
                    warning
                    for warning in backend_warnings
                    if warning.startswith("Numeración de cláusulas") or warning.startswith(self.validator.MISSING_CONTRACT_DATE_MAPPING_WARNING)
                ]
                + reference_warnings
                + self._extract_raw_field_issues(draft)
            )
            if not retryable_issues:
                self._finalize_draft(draft, backend_warnings, preparation_warnings)
                return draft, attempt

            if attempt == max_attempts - 1:
                self._finalize_draft(draft, backend_warnings, preparation_warnings, reference_warnings)
                return draft, attempt

            retry_feedback = retryable_issues

        raise ValidationError("No se pudo generar un borrador valido desde el archivo de referencia.")

    async def _generate_validated_prompt_draft(
        self,
        request: GenerateTemplateDraftRequest,
        *,
        document_type: DocumentType,
        organization_context: dict[str, Any],
    ) -> tuple[TemplateDraftResponse, int]:
        """Generates a prompt-based draft with one validation retry."""
        retry_feedback: list[str] = []
        max_attempts = 2

        for attempt in range(max_attempts):
            draft = await self.draft_generator.generate(
                request=request,
                organization_context=organization_context,
                validation_feedback=retry_feedback or None,
            )
            try:
                preparation_warnings, backend_warnings = self._prepare_and_validate_generated_draft(
                    draft,
                    document_type=document_type,
                    generation_mode=request.generation_mode,
                )
            except ValueError as exc:
                if attempt == max_attempts - 1:
                    raise
                retry_feedback = [str(exc)]
                continue

            raw_field_issues = self._extract_raw_field_issues(draft)
            if raw_field_issues:
                if attempt == max_attempts - 1:
                    self._finalize_draft(draft, backend_warnings, preparation_warnings, raw_field_issues)
                    return draft, attempt
                retry_feedback = raw_field_issues
                continue

            self._finalize_draft(draft, backend_warnings, preparation_warnings)
            return draft, attempt

        raise ValidationError("No se pudo generar un borrador valido a partir de las instrucciones.")

    async def _get_template_or_raise(self, template_id: int, organization_id: int) -> TemplateTable:
        """Loads one template or raises a not found error."""
        template = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        if template is None:
            raise NotFoundError("Plantilla no encontrada")
        return template

    def _prepare_generated_content(
        self,
        content: TemplateContent,
        *,
        document_type: DocumentType,
        generation_mode: TemplateGenerationMode,
    ) -> tuple[TemplateContent, list[str]]:
        """Synchronizes generated content and applies draft post-processing modes."""
        normalized_content = content
        stripped_body_md = self.rendered_contract_formatter.strip_signature_blocks(content.body_md)
        if stripped_body_md != content.body_md:
            normalized_content = content.model_copy(update={"body_md": stripped_body_md})

        synced_content = self.content_synchronizer.sync(normalized_content)
        warnings: list[str] = []

        if document_type == DocumentType.COMPANY:
            if generation_mode == TemplateGenerationMode.ADAPTIVE:
                enriched_content = self._inject_contract_date_clause(synced_content)
                if enriched_content.body_md != synced_content.body_md:
                    synced_content = self.content_synchronizer.sync(enriched_content)
            else:
                self._ensure_explicit_contract_dates(synced_content)

        if document_type == DocumentType.COMPANY and generation_mode == TemplateGenerationMode.STRICT:
            self._ensure_explicit_contract_dates(synced_content)

        return synced_content, warnings

    def _prepare_and_validate_generated_draft(
        self,
        draft: TemplateDraftResponse,
        *,
        document_type: DocumentType,
        generation_mode: TemplateGenerationMode,
    ) -> tuple[list[str], list[str]]:
        """Synchronizes generated content and returns authoritative backend warnings."""
        draft.content, preparation_warnings = self._prepare_generated_content(
            draft.content,
            document_type=document_type,
            generation_mode=generation_mode,
        )
        backend_warnings = self.validator.validate(draft.content, document_type=document_type)
        return preparation_warnings, backend_warnings

    def _filter_stale_ai_warnings(self, warnings: list[str]) -> list[str]:
        """Drops AI-authored warnings that backend recalculates authoritatively."""
        filtered_warnings: list[str] = []
        for warning in warnings:
            if warning == self.validator.MISSING_CONTRACT_DATE_MAPPING_WARNING:
                continue
            if any(pattern.match(warning) for pattern in self.STALE_AI_WARNING_PATTERNS):
                continue
            filtered_warnings.append(warning)
        return filtered_warnings

    def _merge_warnings(self, *warning_groups: list[str]) -> list[str]:
        """Merges warning groups preserving order and removing duplicates."""
        merged_warnings: list[str] = []
        seen: set[str] = set()
        for group in warning_groups:
            for warning in group:
                if warning in seen:
                    continue
                merged_warnings.append(warning)
                seen.add(warning)
        return merged_warnings

    def _finalize_draft(self, draft: TemplateDraftResponse, *warning_groups: list[str]) -> None:
        """Removes internal metadata and keeps backend warnings as the source of truth."""
        self._strip_internal_draft_source(draft)
        draft.warnings = self._merge_warnings(
            self._filter_stale_ai_warnings(draft.warnings),
            *warning_groups,
        )

    def _extract_raw_field_issues(self, draft: TemplateDraftResponse) -> list[str]:
        """Reads raw field issues captured before backend normalization."""
        issues = draft.source.get("field_issues")
        if not isinstance(issues, list):
            return []
        return [str(issue) for issue in issues if str(issue).strip()]

    def _strip_internal_draft_source(self, draft: TemplateDraftResponse) -> None:
        """Removes internal metadata not meant for API consumers."""
        draft.source.pop("field_issues", None)

    def _ensure_explicit_contract_dates(self, content: TemplateContent) -> None:
        """Requires start and end placeholders to be explicit in body_md."""
        mapping = content.contract_date_mapping
        if mapping is None:
            raise ValueError(self.EXPLICIT_CONTRACT_DATES_REQUIRED_MESSAGE)

        placeholders = self.validator.extract(content.body_md)
        if mapping.start_date_field not in placeholders or mapping.end_date_field not in placeholders:
            raise ValueError(self.EXPLICIT_CONTRACT_DATES_REQUIRED_MESSAGE)

    def _inject_contract_date_clause(self, content: TemplateContent) -> TemplateContent:
        """Adds a minimal vigencia clause when the draft has a date mapping but the body does not expose it."""
        mapping = content.contract_date_mapping
        if mapping is None:
            return content

        placeholders = self.validator.extract(content.body_md)
        has_start = mapping.start_date_field in placeholders
        has_end = mapping.end_date_field in placeholders
        if has_start and has_end:
            return content

        start_placeholder = f"{{{{ {mapping.start_date_field} }}}}"
        end_placeholder = f"{{{{ {mapping.end_date_field} }}}}"
        if not has_start and not has_end:
            clause_text = (
                f"**VIGENCIA DEL CONTRATO.-** La vigencia del presente contrato inicia el {start_placeholder} y concluye el {end_placeholder}."
            )
        elif not has_start:
            clause_text = f"**INICIO DE VIGENCIA.-** La vigencia del presente contrato inicia el {start_placeholder}."
        else:
            clause_text = f"**FIN DE VIGENCIA.-** La vigencia del presente contrato concluye el {end_placeholder}."

        return content.model_copy(update={"body_md": self._insert_clause_before_closing(content.body_md, clause_text)})

    def _insert_clause_before_closing(self, body_md: str, clause_text: str) -> str:
        """Places the generated clause before the closing section when possible."""
        stripped_body = body_md.rstrip()
        for pattern in self.CONTRACT_CLOSING_PATTERNS:
            match = re.search(pattern, stripped_body)
            if match is None:
                continue
            prefix = stripped_body[: match.start()].rstrip()
            suffix = stripped_body[match.start() :].lstrip()
            return f"{prefix}\n\n{clause_text}\n\n{suffix}" if prefix else f"{clause_text}\n\n{suffix}"
        return f"{stripped_body}\n\n{clause_text}" if stripped_body else clause_text

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
        template_format_id: int,
        content: TemplateContent,
    ) -> TemplateTable:
        """Builds the base template entity."""
        return TemplateTable(
            organization_id=organization_id,
            name=name,
            description=description,
            document_type=document_type,
            template_format_id=template_format_id,
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

    async def _get_template_format_or_raise(
        self,
        document_type: DocumentType,
        format_code: str,
    ) -> TemplateFormatTable:
        """Loads one active template format or raises a validation error."""
        template_format = await self.template_format_repo.get_by_document_type_and_code(
            document_type=document_type,
            format_code=format_code,
        )
        if template_format is None:
            raise ValidationError(f"format_code '{format_code}' no es válido para document_type '{document_type.value}'.")
        return template_format

    async def _get_template_format_by_id(self, template_format_id: int | None) -> TemplateFormatTable | None:
        """Loads one template format by identifier when present."""
        if template_format_id is None:
            return None
        return await self.template_format_repo.get_by_id(template_format_id)

    def _apply_format_defaults(
        self,
        request: GenerateTemplateDraftRequest,
        document_type: DocumentType,
        template_format: TemplateFormatTable,
    ) -> GenerateTemplateDraftRequest:
        """Applies default metadata for the selected format."""
        return request.model_copy(
            update={
                "document_type": document_type,
                "name": request.name or self._resolve_template_default_name(template_format),
                "description": request.description if request.description is not None else template_format.default_description,
            }
        )

    def _build_template_format_response(self, template_format: TemplateFormatTable) -> TemplateFormatResponse:
        """Builds one template-format response payload."""
        return TemplateFormatResponse(
            id=template_format.id,
            document_type=template_format.document_type,
            format_code=template_format.format_code,
            label=template_format.label,
            default_name=self._resolve_template_default_name(template_format),
            default_description=template_format.default_description,
        )

    def _resolve_template_default_name(self, template_format: TemplateFormatTable) -> str:
        """Resolves the default visible name of a template format."""
        return (template_format.default_name or template_format.label).strip()

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
        labor_score = self._score_classifier_patterns(normalized_text, self.LABOR_CLASSIFIER_PATTERNS)
        company_score = self._score_classifier_patterns(normalized_text, self.COMPANY_CLASSIFIER_PATTERNS)

        if labor_score == 0 and company_score == 0:
            return None
        if company_score >= labor_score + 2:
            return DocumentType.COMPANY
        if labor_score >= company_score + 2:
            return DocumentType.LABOR
        return None

    def _score_classifier_patterns(self, text: str, patterns: tuple[tuple[str, int], ...]) -> int:
        """Scores a normalized reference text using weighted regex patterns."""
        return sum(weight for pattern, weight in patterns if re.search(pattern, text))

    def _normalize_reference_text(self, value: str) -> str:
        """Normalizes extracted text for heuristic matching."""
        normalized = unicodedata.normalize("NFD", value)
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return re.sub(r"\s+", " ", normalized).strip().lower()

    def _build_time_payload(self) -> dict[str, int | str]:
        """Builds automatic date placeholders."""
        return build_signature_time_payload(datetime.now())

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
        if field.type == "time":
            return "09:00"
        if field.type == "number":
            return 1000
        if field.type == "boolean":
            return True
        return field.label
