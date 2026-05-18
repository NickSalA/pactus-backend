"""Service layer for template reads and contract generation."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from .....core.exceptions.base import ForbiddenError, ValidationError
from ....documents.domain import DocumentType
from ....documents.domain.access_policy import can_write_document_type
from ....users.domain.value_objs import UserRole
from ...domain.entities import TemplateContent, TemplateFormatTable, TemplateTable
from ...domain.formats import normalize_format_code
from ...domain.value_objs import TemplateState
from ..dto import TemplateResponse, build_template_response
from ..repositories.base_generate import IDocumentGenerator
from ..repositories.base_relational import IDocumentModuleAdapter, IOrganizationRepository, ITemplateFormatRepository, ITemplateRepository
from ..repositories.base_render import ITemplateRenderer
from .rendered_contract_formatter import RenderedContractFormatter
from .template_content_synchronizer import TemplateContentSynchronizer
from .template_runtime_payloads import build_signature_time_payload


class TemplateService:
    def __init__(
        self,
        template_repo: ITemplateRepository,
        template_format_repo: ITemplateFormatRepository,
        organization_repo: IOrganizationRepository,
        renderer: ITemplateRenderer,
        document_generator: IDocumentGenerator,
        document_adapter: IDocumentModuleAdapter,
    ):
        """Stores dependencies for template reads and rendering."""
        self.template_repo = template_repo
        self.template_format_repo = template_format_repo
        self.organization_repo = organization_repo
        self.renderer = renderer
        self.document_generator = document_generator
        self.document_adapter = document_adapter
        self.content_synchronizer = TemplateContentSynchronizer()
        self.rendered_contract_formatter = RenderedContractFormatter()

    async def generate_contract(
        self,
        template_id: int,
        organization_id: int,
        form_data: dict[str, Any],
        user_role: UserRole | None,
    ):
        """Generates a contract from a published template."""
        template = await self._get_and_validate_template(template_id, organization_id, user_role)

        template_content = (
            self.content_synchronizer.sync(TemplateContent.model_validate(template.content)) if isinstance(template.content, dict) else None
        )
        now = datetime.now()
        service_items = form_data.get("service_items") or [] if template.document_type == DocumentType.COMPANY else []
        start_date, end_date = self._resolve_generated_dates(
            form_data=form_data,
            now=now,
            template_content=template_content,
            require_explicit_dates=bool(service_items),
        )

        org_data = await self.organization_repo.get_organization_data(organization_id=organization_id)
        template_format = await self.template_format_repo.get_by_id(template.template_format_id) if template.template_format_id is not None else None

        master_dict = {**form_data, **org_data, **build_signature_time_payload(now)}
        if template_content is not None:
            self._validate_required_fields(template_content=template_content, payload=master_dict)

        body_md = template_content.body_md if template_content is not None else template.content
        md_final = await self.renderer.render(template_md=body_md, payload=master_dict)
        md_final = self.rendered_contract_formatter.format(md_final, document_type=template.document_type, payload=master_dict)

        pdf_bytes = await self.document_generator.generate_pdf(markdown_content=md_final)

        company_contract, labor_contract, counterparty_name = self._extract_specific_contract_data(template.document_type, form_data)

        generated_file_name = self._generate_file_name(template.name, counterparty_name, now)

        document_payload: dict[str, Any] = {
            "organization_id": organization_id,
            "type": template_format.format_code if template_format is not None else template.document_type.value.lower(),
            "contract_type": template.document_type,
            "state": "PENDING_SIGNATURE",
            "content": pdf_bytes,
            "start_date": start_date,
            "end_date": end_date,
            "folder_id": form_data.get("folder_id"),
            "service_items": service_items,
            "form_data": master_dict,
            "file_name": generated_file_name,
            "company_contract": company_contract,
            "labor_contract": labor_contract,
        }
        return await self.document_adapter.save_generated_document(
            document_payload=document_payload,
            file=pdf_bytes,
            user_role=user_role,
        )

    async def _get_and_validate_template(self, template_id: int, organization_id: int, user_role: UserRole | None) -> TemplateTable:
        template = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        if not template:
            raise ValueError("Template not found or does not belong to the organization.")
        if template.state != TemplateState.PUBLISHED:
            raise ValueError("Solo se pueden generar documentos desde plantillas en estado PUBLISHED.")
        if not can_write_document_type(user_role=user_role, document_type=template.document_type):
            raise ForbiddenError("No tiene permisos para generar contratos con esta plantilla")
        return template

    def _extract_specific_contract_data(
        self, document_type: DocumentType, form_data: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
        company_contract = None
        labor_contract = None
        counterparty_name = "contraparte"

        if document_type == DocumentType.COMPANY:
            counterparty_name = form_data.get("cliente_nombre") or "cliente"
            company_contract = {
                "ruc": form_data.get("cliente_ruc") or form_data.get("empresa_ruc") or form_data.get("ruc"),
                "client": counterparty_name,
            }
        elif document_type == DocumentType.LABOR:
            counterparty_name = form_data.get("trabajador_nombre") or "trabajador"
            try:
                salary_value = float(form_data.get("salario") or form_data.get("remuneracion") or 0)
            except (TypeError, ValueError):
                salary_value = None

            labor_contract = {
                "worker_name": counterparty_name,
                "worker_document_number": form_data.get("trabajador_dni"),
                "position": form_data.get("cargo"),
                "salary_value": salary_value or None,
                "salary_currency": form_data.get("moneda"),
                "salary_periodicity": form_data.get("periodicidad"),
                "contract_modality": form_data.get("modalidad"),
            }

        return company_contract, labor_contract, counterparty_name

    def _generate_file_name(self, template_name: str, counterparty_name: str, now: datetime) -> str:
        base_name = template_name.replace(" ", "_").lower()
        safe_counterparty = counterparty_name.replace(" ", "_").lower()
        timestamp = int(now.timestamp())
        return f"{base_name}_{safe_counterparty}_{timestamp}.pdf"

    async def get_template(
        self,
        template_id: int,
        organization_id: int,
        user_role: UserRole | None = None,
    ) -> TemplateResponse | None:
        """Loads one template visible to the current role."""
        template = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        if template is None:
            return None
        if user_role not in (None, UserRole.ADMIN) and not can_write_document_type(user_role=user_role, document_type=template.document_type):
            return None

        template_format = await self.template_format_repo.get_by_id(template.template_format_id) if template.template_format_id else None
        return self._build_synced_template_response(template, template_format=template_format)

    async def list_templates(
        self,
        organization_id: int,
        user_role: UserRole | None = None,
        document_type: DocumentType | None = None,
        format_code: str | None = None,
        state: TemplateState | None = None,
    ) -> Sequence[TemplateResponse]:
        """Lists templates visible to the current role with optional filters."""
        templates = list(await self.template_repo.list_by_organization(organization_id=organization_id))
        if user_role not in (None, UserRole.ADMIN):
            if document_type is not None and not can_write_document_type(user_role=user_role, document_type=document_type):
                raise ForbiddenError(f"No tiene permisos para listar plantillas de tipo {document_type.value}.")
            templates = [template for template in templates if can_write_document_type(user_role=user_role, document_type=template.document_type)]

        if document_type is not None:
            templates = [template for template in templates if template.document_type == document_type]

        if state is not None:
            templates = [template for template in templates if template.state == state]

        format_map = await self._load_format_map(templates)
        if format_code is not None:
            normalized_format_code = normalize_format_code(format_code)
            templates = [
                template
                for template in templates
                if template.template_format_id is not None
                and template.template_format_id in format_map
                and format_map[template.template_format_id].format_code == normalized_format_code
            ]

        return [
            self._build_synced_template_response(
                template,
                template_format=format_map.get(template.template_format_id) if template.template_format_id is not None else None,
            )
            for template in templates
        ]

    def _build_synced_template_response(
        self,
        template: TemplateTable,
        *,
        template_format: TemplateFormatTable | None,
    ) -> TemplateResponse:
        """Serializes templates after normalizing derived placeholders."""
        if isinstance(template.content, dict):
            template = template.model_copy(
                update={"content": self.content_synchronizer.sync(TemplateContent.model_validate(template.content)).model_dump(mode="python")}
            )
        return build_template_response(template, template_format=template_format)

    async def _load_format_map(self, templates: Sequence[TemplateTable]) -> dict[int, TemplateFormatTable]:
        """Loads template formats referenced by the provided templates."""
        format_ids = sorted({template.template_format_id for template in templates if template.template_format_id is not None})
        formats = await self.template_format_repo.list_by_ids(format_ids)
        return {template_format.id: template_format for template_format in formats}

    def _resolve_generated_dates(
        self,
        form_data: dict[str, Any],
        now: datetime,
        template_content: TemplateContent | None,
        *,
        require_explicit_dates: bool = False,
    ) -> tuple[str, str]:
        """Normaliza fechas de vigencia desde los nombres más comunes del payload."""
        mapping = template_content.contract_date_mapping if template_content is not None else None
        if mapping is not None:
            start_date = self._first_non_empty_value(form_data, mapping.start_date_field)
            end_date = self._first_non_empty_value(form_data, mapping.end_date_field)
        else:
            start_date = self._first_non_empty_value(
                form_data,
                "contrato_fecha_inicio",
                "contract_start_date",
                "fecha_inicio",
                "start_date",
            )
            end_date = self._first_non_empty_value(
                form_data,
                "contrato_fecha_fin",
                "contract_end_date",
                "fecha_fin",
                "end_date",
            )
        if require_explicit_dates and (start_date is None or end_date is None):
            mapping_hint = (
                f"Verifica que el payload incluya los campos configurados en la plantilla: {mapping.start_date_field} y {mapping.end_date_field}."
                if mapping is not None
                else "Verifica que la plantilla exponga y mapee los campos de inicio y fin del contrato."
            )
            raise ValidationError(f"No se pudieron resolver las fechas de vigencia del contrato desde la plantilla. {mapping_hint}")
        fallback = now.date().isoformat()
        return start_date or fallback, end_date or fallback

    @staticmethod
    def _first_non_empty_value(payload: dict[str, Any], *keys: str) -> str | None:
        """Devuelve el primer valor no vacío entre varias claves posibles."""
        for key in keys:
            value = payload.get(key)
            if TemplateService._is_empty_value(value):
                continue
            return str(value)
        return None

    def _validate_required_fields(self, *, template_content: TemplateContent, payload: dict[str, Any]) -> None:
        """Ensures every required template field has a concrete value before rendering."""
        if missing_fields := [
            field.label
            for field in template_content.fields + template_content.operational_fields
            if field.required and self._is_empty_value(payload.get(field.key))
        ]:
            raise ValidationError("Faltan campos obligatorios para generar el contrato: " + ", ".join(missing_fields))

    @staticmethod
    def _is_empty_value(value: Any) -> bool:
        """Returns True when the provided value should be considered missing."""
        if value is None:
            return True
        return value.strip() == "" if isinstance(value, str) else False
