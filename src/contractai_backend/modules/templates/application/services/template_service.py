"""Service layer for template reads and contract generation."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from .....core.exceptions.base import ForbiddenError
from ....documents.domain import DocumentType
from ....documents.domain.access_policy import can_write_document_type
from ....users.domain.value_objs import UserRole
from ...api.schemas import TemplateResponse, build_template_response
from ...domain.entities import TemplateFormatTable, TemplateTable
from ...domain.formats import normalize_format_code
from ...domain.value_objs import TemplateState
from ..repositories.base_generate import IDocumentGenerator
from ..repositories.base_relational import IDocumentModuleAdapter, IOrganizationRepository, ITemplateFormatRepository, ITemplateRepository
from ..repositories.base_render import ITemplateRenderer


class TemplateService:
    def __init__(  # noqa: PLR0913
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

    async def generate_contract(
        self,
        template_id: int,
        organization_id: int,
        form_data: dict[str, Any],
        user_role: UserRole | None,
    ):
        """Generates a contract from a published template."""
        template = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        if not template:
            raise ValueError("Template not found or does not belong to the organization.")
        if template.state != TemplateState.PUBLISHED:
            raise ValueError("Solo se pueden generar documentos desde plantillas en estado PUBLISHED.")
        if not can_write_document_type(user_role=user_role, document_type=template.document_type):
            raise ForbiddenError("No tiene permisos para generar contratos con esta plantilla")

        org_data = await self.organization_repo.get_organization_data(organization_id=organization_id)
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
        time_auto: dict[str, int | str] = {"day_sign": now.day, "month_sign": months[now.month - 1], "year_sign": now.year}
        master_dict: dict[str, Any | int | str] = {**form_data, **org_data, **time_auto}
        body_md = template.content.get("body_md", "") if isinstance(template.content, dict) else template.content
        md_final = await self.renderer.render(template_md=body_md, payload=master_dict)

        pdf_bytes = await self.document_generator.generate_pdf(markdown_content=md_final)
        cliente_nombre = form_data.get("trabajador_nombre") or form_data.get("cliente_nombre") or "cliente"
        base_name = template.name.replace(" ", "_").lower()
        cliente_seguro = cliente_nombre.replace(" ", "_").lower()
        timestamp = int(now.timestamp())
        generated_file_name = f"{base_name}_{cliente_seguro}_{timestamp}.pdf"
        service_items = form_data.get("service_items", []) if template.document_type == DocumentType.COMPANY else []
        start_date, end_date = self._resolve_generated_dates(form_data=form_data, now=now)
        document_payload: dict[str, int | str | bytes | Any | dict[str, Any | int | str]] = {
            "organization_id": organization_id,
            "template_id": template_id,
            "name": f"{template.name} - {cliente_nombre}",
            "client": cliente_nombre,
            "type": template.document_type,
            "state": "PENDING_SIGNATURE",
            "content": pdf_bytes,
            "start_date": start_date,
            "end_date": end_date,
            "folder_id": form_data.get("folder_id"),
            "service_items": service_items,
            "form_data": master_dict,
            "file_name": generated_file_name,
        }
        return await self.document_adapter.save_generated_document(
            document_payload=document_payload,
            file=pdf_bytes,
            user_role=user_role,
        )

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
        return build_template_response(template, template_format=template_format)

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

        return [build_template_response(template, template_format=format_map.get(template.template_format_id)) for template in templates]

    async def _load_format_map(self, templates: Sequence[TemplateTable]) -> dict[int, TemplateFormatTable]:
        """Loads template formats referenced by the provided templates."""
        format_ids = sorted({template.template_format_id for template in templates if template.template_format_id is not None})
        formats = await self.template_format_repo.list_by_ids(format_ids)
        return {template_format.id: template_format for template_format in formats}

    def _resolve_generated_dates(self, form_data: dict[str, Any], now: datetime) -> tuple[str, str]:
        """Normaliza fechas de vigencia desde los nombres más comunes del payload."""
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
        fallback = now.date().isoformat()
        return start_date or fallback, end_date or fallback

    @staticmethod
    def _first_non_empty_value(payload: dict[str, Any], *keys: str) -> str | None:
        """Devuelve el primer valor no vacío entre varias claves posibles."""
        for key in keys:
            value = payload.get(key)
            if value in (None, ""):
                continue
            return str(value)
        return None
