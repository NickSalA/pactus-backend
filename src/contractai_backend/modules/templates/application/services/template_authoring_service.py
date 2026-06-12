"""Service for generating, validating and managing templates."""

from datetime import datetime
from typing import Any

from ....audit.application.services import TemplateActivityService
from ....documents.application.repositories import DocumentExtractor
from ....documents.domain import DocumentType
from ....documents.domain.access_policy import can_write_document_type
from ....users.domain.entities import UserTable
from ....users.domain.value_objs import UserRole
from ...domain.entities import TemplateContent, TemplateField, TemplateFormatTable, TemplateTable
from ...domain.exceptions import (
    TemplateAccessDeniedError,
    TemplateNotFoundError,
    TemplateStateError,
    TemplateValidationError,
)
from ...domain.value_objs import TemplateState
from ..dto import (
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
from ..repositories import IOrganizationRepository, ITemplateFormatRepository, ITemplateRenderer, ITemplateRepository
from .rendered_contract_formatter import RenderedContractFormatter
from .template_content_synchronizer import TemplateContentSynchronizer
from .template_draft_service import TemplateDraftService
from .template_placeholder_validator import TemplatePlaceholderValidator
from .template_reference_preprocessor import TemplateReferencePreprocessor
from .template_reference_service import TemplateReferenceService
from .template_runtime_payloads import build_signature_time_payload

ROLE_LOCKED_DOCUMENT_TYPES: dict[UserRole, DocumentType] = {
    UserRole.HR: DocumentType.LABOR,
    UserRole.MANAGER: DocumentType.COMPANY,
}


class TemplateAuthoringService:
    """Coordinates template authoring flows and access control."""

    def __init__(
        self,
        template_repo: ITemplateRepository,
        template_format_repo: ITemplateFormatRepository,
        organization_repo: IOrganizationRepository,
        renderer: ITemplateRenderer,
        extractor: DocumentExtractor,
        activity_service: TemplateActivityService,
        draft_service: TemplateDraftService,
        reference_service: TemplateReferenceService,
    ):
        """Stores dependencies for template authoring."""
        self.template_repo = template_repo
        self.template_format_repo = template_format_repo
        self.organization_repo = organization_repo
        self.renderer = renderer
        self.extractor = extractor
        self.activity_service = activity_service
        self.draft_service = draft_service
        self.reference_service = reference_service

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
            raise TemplateAccessDeniedError("No tiene permisos para gestionar plantillas")

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

        draft = await self.draft_service.generate_draft_from_prompt(
            request=resolved_request,
            document_type=document_type,
            organization_id=organization_id,
        )
        return draft, document_type

    async def generate_and_save_draft_from_prompt(
        self,
        request: GenerateTemplateDraftRequest,
        actor: UserTable,
    ) -> PersistedTemplateDraftResponse:
        """Generates and persists a draft from prompt data."""
        draft, document_type = await self.generate_draft_from_prompt(
            request=request,
            organization_id=actor.organization_id,
            user_role=actor.role,
        )
        template = await self._persist_draft(
            draft=draft,
            actor=actor,
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
        self.reference_service.validate_reference_document_type(
            reference_context=reference_context,
            expected_document_type=document_type,
        )

        draft = await self.draft_service.generate_draft_from_file(
            request=resolved_request,
            document_type=document_type,
            reference_context=reference_context,
            filename=filename,
            organization_id=organization_id,
        )
        return draft, document_type

    async def generate_and_save_draft_from_file(
        self,
        request: GenerateTemplateDraftRequest,
        file_content: bytes,
        filename: str,
        actor: UserTable,
    ) -> PersistedTemplateDraftResponse:
        """Generates and persists a draft from a reference file."""
        draft, document_type = await self.generate_draft_from_file(
            request=request,
            file_content=file_content,
            filename=filename,
            organization_id=actor.organization_id,
            user_role=actor.role,
        )
        template = await self._persist_draft(
            draft=draft,
            actor=actor,
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

    async def update_template(
        self,
        template_id: int,
        request: UpdateTemplateRequest,
        actor: UserTable,
    ) -> TemplateResponse:
        """Updates a draft template without changing its base format."""
        template = await self._get_template_or_raise(template_id=template_id, organization_id=actor.organization_id)
        self._ensure_can_author_document_type(user_role=actor.role, document_type=template.document_type)
        if template.state != TemplateState.DRAFT:
            raise TemplateStateError("Solo se pueden editar plantillas en estado DRAFT.")

        previous_state = str(template.state.value) if template.state else None
        fields_set = request.model_fields_set

        if "content" in fields_set:
            if request.content is None:
                raise TemplateValidationError("Content cannot be null")
            synced_content = self.content_synchronizer.sync(request.content)
            self.validator.validate(synced_content, document_type=template.document_type)
            template.content = synced_content.model_dump(mode="python")
        if "name" in fields_set:
            if request.name is None:
                raise TemplateValidationError("Name cannot be null")
            template.name = request.name
        if "description" in fields_set:
            template.description = request.description

        updated_template = await self.template_repo.update(entity=template)
        await self.activity_service.record_updated(actor=actor, template=updated_template, previous_state=previous_state)
        template_format = await self._get_template_format_by_id(template.template_format_id)
        return build_template_response(updated_template, template_format=template_format)

    async def publish_template(
        self,
        template_id: int,
        actor: UserTable,
    ) -> TemplateResponse:
        """Publishes a draft template."""
        template = await self._get_template_or_raise(template_id=template_id, organization_id=actor.organization_id)
        self._ensure_can_author_document_type(user_role=actor.role, document_type=template.document_type)
        if template.state != TemplateState.DRAFT:
            raise TemplateStateError("Solo se pueden publicar plantillas en estado DRAFT.")
        template_format = await self._get_template_format_by_id(template.template_format_id)
        if template_format is None:
            raise TemplateValidationError("La plantilla debe tener un formato válido antes de publicarse.")
        await self._get_template_format_or_raise(document_type=template.document_type, format_code=template_format.format_code)

        content = self.content_synchronizer.sync(TemplateContent.model_validate(template.content))
        self.validator.validate(
            content,
            document_type=template.document_type,
            require_contract_date_mapping=template.document_type == DocumentType.COMPANY,
        )
        content.version = self._resolve_publish_version(content.version)

        previous_state = str(template.state.value) if template.state else None
        template.content = content.model_dump(mode="python")
        template.state = TemplateState.PUBLISHED
        published_template = await self.template_repo.publish(entity=template)
        await self.activity_service.record_updated(actor=actor, template=published_template, previous_state=previous_state)
        return build_template_response(published_template, template_format=template_format)

    async def archive_template(
        self,
        template_id: int,
        actor: UserTable,
    ) -> TemplateResponse:
        """Archives a template that should no longer be used."""
        template = await self._get_template_or_raise(template_id=template_id, organization_id=actor.organization_id)
        self._ensure_can_author_document_type(user_role=actor.role, document_type=template.document_type)
        if template.state == TemplateState.ARCHIVED:
            raise TemplateStateError("La plantilla ya se encuentra archivada.")

        previous_state = str(template.state.value) if template.state else None
        template.state = TemplateState.ARCHIVED
        archived_template = await self.template_repo.update(entity=template)
        await self.activity_service.record_archived(actor=actor, template=archived_template, previous_state=previous_state)
        template_format = await self._get_template_format_by_id(template.template_format_id)
        return build_template_response(archived_template, template_format=template_format)

    async def _persist_draft(
        self,
        draft: TemplateDraftResponse,
        actor: UserTable,
        document_type: DocumentType,
        format_code: str,
    ) -> TemplateResponse:
        """Persists a generated draft template."""
        template_format = await self._get_template_format_or_raise(document_type=document_type, format_code=format_code)
        template = self._build_template_entity(
            organization_id=actor.organization_id,
            name=draft.name,
            description=draft.description,
            document_type=document_type,
            template_format_id=template_format.id,
            content=draft.content,
        )
        saved_template = await self.template_repo.save(entity=template)
        await self.activity_service.record_created(actor=actor, template=saved_template)
        return build_template_response(saved_template, template_format=template_format)

    async def _get_template_or_raise(self, template_id: int, organization_id: int) -> TemplateTable:
        """Loads one template or raises a not found error."""
        template = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        if template is None:
            raise TemplateNotFoundError("Plantilla no encontrada")
        return template

    def _resolve_publish_version(self, version: str | None) -> str:
        """Normalizes the version on publish."""
        normalized_version = (version or "").strip()
        return normalized_version or "1.0"

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
                raise TemplateValidationError("document_type es obligatorio para usuarios ADMIN.")
            return requested_document_type

        locked_document_type = ROLE_LOCKED_DOCUMENT_TYPES.get(user_role)
        if locked_document_type is None:
            raise TemplateAccessDeniedError("No tiene permisos para gestionar plantillas")

        if requested_document_type is not None and requested_document_type != locked_document_type:
            raise TemplateAccessDeniedError(f"No tiene permisos para crear plantillas de tipo {requested_document_type.value}.")

        return locked_document_type

    def _ensure_can_author_document_type(self, user_role: UserRole, document_type: DocumentType) -> None:
        """Checks whether the current role can author templates for the type."""
        if not can_write_document_type(user_role=user_role, document_type=document_type):
            raise TemplateAccessDeniedError(f"No tiene permisos para gestionar plantillas de tipo {document_type.value}.")

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
            raise TemplateValidationError(f"format_code '{format_code}' no es válido para document_type '{document_type.value}'.")
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

    def _build_time_payload(self) -> dict[str, int | str]:
        """Builds automatic date placeholders."""
        return build_signature_time_payload(datetime.now())

    def _build_mock_payload(self, fields: list[TemplateField]) -> dict[str, Any]:
        """Builds mock payload values for preview."""
        payload: dict[str, Any] = {field.key: self._mock_value(field) for field in fields}
        return payload

    def _mock_value(self, field: TemplateField) -> Any:
        """Builds a mock value by field type."""
        if field.type == "date":
            return "2026-01-01"
        if field.type == "time":
            return "09:00"
        if field.type == "number":
            return 1000
        return True if field.type == "boolean" else field.label
