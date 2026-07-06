"""Service for generating and post-processing template drafts using LLM."""

import re
from typing import Any

from ....documents.domain import DocumentType
from ...domain.entities import TemplateContent
from ...domain.exceptions import TemplateValidationError
from ...domain.patterns import CONTRACT_CLOSING_PATTERNS, STALE_AI_WARNING_PATTERNS
from ...domain.value_objs import TemplateGenerationMode
from ..dto import GenerateTemplateDraftRequest, TemplateDraftResponse
from ..repositories import IOrganizationRepository
from ..repositories.base_draft_generator import ITemplateDraftGenerator
from .rendered_contract_formatter import RenderedContractFormatter
from .template_content_synchronizer import TemplateContentSynchronizer
from .template_placeholder_validator import TemplatePlaceholderValidator
from .template_reference_preprocessor import TemplateReferenceContext


class TemplateDraftService:
    """Coordinates draft generation and post-processing (retry loops, vigencia clauses)."""

    EXPLICIT_CONTRACT_DATES_REQUIRED_MESSAGE = (
        "La plantilla de referencia no expone fechas de inicio y fin del contrato de forma explícita. "
        "Usa generation_mode='adaptive' para permitir que la IA las complete."
    )

    def __init__(
        self,
        draft_generator: ITemplateDraftGenerator,
        organization_repo: IOrganizationRepository,
    ):
        """Initializes dependencies for template draft orchestrations."""
        self.draft_generator = draft_generator
        self.organization_repo = organization_repo
        self.content_synchronizer = TemplateContentSynchronizer()
        self.validator = TemplatePlaceholderValidator()
        self.rendered_contract_formatter = RenderedContractFormatter()

    async def generate_draft_from_prompt(
        self,
        request: GenerateTemplateDraftRequest,
        document_type: DocumentType,
        organization_id: int,
    ) -> TemplateDraftResponse:
        """Generates a prompt-based draft with validation retry."""
        organization_context = await self.build_organization_context(organization_id=organization_id)
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
            except TemplateValidationError as exc:
                if attempt == max_attempts - 1:
                    raise
                retry_feedback = [str(exc)]
                continue

            if raw_field_issues := self._extract_raw_field_issues(draft):
                if attempt == max_attempts - 1:
                    self._finalize_draft(draft, backend_warnings, preparation_warnings, raw_field_issues)
                    draft.source = {
                        **draft.source,
                        "mode": draft.source.get("mode", "prompt"),
                        "generation_mode": request.generation_mode.value,
                        "retries_used": attempt,
                    }
                    return draft
                retry_feedback = raw_field_issues
                continue

            self._finalize_draft(draft, backend_warnings, preparation_warnings)
            draft.source = {
                **draft.source,
                "mode": draft.source.get("mode", "prompt"),
                "generation_mode": request.generation_mode.value,
                "retries_used": attempt,
            }
            return draft

        raise TemplateValidationError("No se pudo generar un borrador valido a partir de las instrucciones.")

    async def generate_draft_from_file(
        self,
        request: GenerateTemplateDraftRequest,
        document_type: DocumentType,
        reference_context: TemplateReferenceContext,
        filename: str,
        organization_id: int,
    ) -> TemplateDraftResponse:
        """Generates a file-based draft with one structural retry."""
        organization_context = await self.build_organization_context(organization_id=organization_id)
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
            except TemplateValidationError as exc:
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
                self._set_file_source_metadata(
                    draft=draft,
                    filename=filename,
                    generation_mode=request.generation_mode.value,
                    reference_context=reference_context,
                    detected_document_type=document_type.value,
                    retries_used=attempt,
                )
                return draft

            if attempt == max_attempts - 1:
                self._finalize_draft(draft, backend_warnings, preparation_warnings, reference_warnings)
                self._set_file_source_metadata(
                    draft=draft,
                    filename=filename,
                    generation_mode=request.generation_mode.value,
                    reference_context=reference_context,
                    detected_document_type=document_type.value,
                    retries_used=attempt,
                )
                return draft

            retry_feedback = retryable_issues

        raise TemplateValidationError("No se pudo generar un borrador valido desde el archivo de referencia.")

    async def build_organization_context(self, organization_id: int) -> dict[str, Any]:
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

    def _finalize_draft(self, draft: TemplateDraftResponse, *warning_groups: list[str]) -> None:
        """Removes internal metadata and keeps backend warnings as the source of truth."""
        self._strip_internal_draft_source(draft)
        draft.warnings = self._merge_warnings(
            self._filter_stale_ai_warnings(draft.warnings),
            *warning_groups,
        )

    def _strip_internal_draft_source(self, draft: TemplateDraftResponse) -> None:
        """Removes internal metadata not meant for API consumers."""
        draft.source.pop("field_issues", None)

    def _extract_raw_field_issues(self, draft: TemplateDraftResponse) -> list[str]:
        """Reads raw field issues captured before backend normalization."""
        issues = draft.source.get("field_issues")
        if not isinstance(issues, list):
            return []
        return [str(issue) for issue in issues if str(issue).strip()]

    def _filter_stale_ai_warnings(self, warnings: list[str]) -> list[str]:
        """Drops AI-authored warnings that backend recalculates authoritatively."""
        filtered_warnings: list[str] = []
        for warning in warnings:
            if warning == self.validator.MISSING_CONTRACT_DATE_MAPPING_WARNING:
                continue
            if any(pattern.match(warning) for pattern in STALE_AI_WARNING_PATTERNS):
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

    def _ensure_explicit_contract_dates(self, content: TemplateContent) -> None:
        """Requires start and end placeholders to be explicit in body_md."""
        mapping = content.contract_date_mapping
        if mapping is None:
            raise TemplateValidationError(self.EXPLICIT_CONTRACT_DATES_REQUIRED_MESSAGE)

        placeholders = self.validator.extract(content.body_md)
        if mapping.start_date_field not in placeholders or mapping.end_date_field not in placeholders:
            raise TemplateValidationError(self.EXPLICIT_CONTRACT_DATES_REQUIRED_MESSAGE)

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
        for pattern in CONTRACT_CLOSING_PATTERNS:
            match = re.search(pattern, stripped_body)
            if match is None:
                continue
            prefix = stripped_body[: match.start()].rstrip()
            suffix = stripped_body[match.start() :].lstrip()
            return f"{prefix}\n\n{clause_text}\n\n{suffix}" if prefix else f"{clause_text}\n\n{suffix}"
        return f"{stripped_body}\n\n{clause_text}" if stripped_body else clause_text

    def _set_file_source_metadata(
        self,
        draft: TemplateDraftResponse,
        filename: str,
        generation_mode: str,
        reference_context: TemplateReferenceContext,
        detected_document_type: str,
        retries_used: int,
    ) -> None:
        """Sets the fully detailed draft source for file references."""
        draft.source = {
            "mode": "file_reference",
            "filename": filename,
            "generation_mode": generation_mode,
            "reference_mode": reference_context.mode,
            "detected_document_type": detected_document_type,
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
