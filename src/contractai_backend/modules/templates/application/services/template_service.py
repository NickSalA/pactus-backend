"""Service layer for handling template-related operations, including contract generation based on templates and organization data."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from .....core.exceptions.base import ForbiddenError
from ....documents.domain import DocumentType
from ....documents.domain.access_policy import can_write_document_type
from ....users.domain.value_objs import UserRole
from ...domain.entities import TemplateTable
from ...domain.value_objs import TemplateState
from ..repositories.base_generate import IDocumentGenerator
from ..repositories.base_relational import IDocumentModuleAdapter, IOrganizationRepository, ITemplateRepository
from ..repositories.base_render import ITemplateRenderer


class TemplateService:
    LABOR_CONTRACT_NAME_PREFIX = "Contrato Estándar de Trabajador"

    def __init__(
        self,
        template_repo: ITemplateRepository,
        organization_repo: IOrganizationRepository,
        renderer: ITemplateRenderer,
        document_generator: IDocumentGenerator,
        document_adapter: IDocumentModuleAdapter,
    ):
        """Stores dependencies for template reads and rendering."""
        self.template_repo: ITemplateRepository = template_repo
        self.organization_repo: IOrganizationRepository = organization_repo
        self.renderer: ITemplateRenderer = renderer
        self.document_generator: IDocumentGenerator = document_generator
        self.document_adapter: IDocumentModuleAdapter = document_adapter

    @classmethod
    def _build_labor_contract_name(cls, worker_name: str | None) -> str:
        normalized_worker_name = worker_name.strip() if isinstance(worker_name, str) else ""
        if normalized_worker_name:
            return f"{cls.LABOR_CONTRACT_NAME_PREFIX} - {normalized_worker_name}"
        return cls.LABOR_CONTRACT_NAME_PREFIX

    async def generate_contract(self, template_id: int, organization_id: int, form_data: dict[str, Any],
        user_role: UserRole | None):
        """Genera un contrato a partir de una plantilla."""
        template: TemplateTable | None = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        if not template:
            raise ValueError("Template not found or does not belong to the organization.")
        if template.state != TemplateState.PUBLISHED:
            raise ValueError("Solo se pueden generar documentos desde plantillas en estado PUBLISHED.")
        if not can_write_document_type(user_role=user_role, document_type=template.document_type):
            raise ForbiddenError("No tiene permisos para generar contratos con esta plantilla")
        org_data = await self.organization_repo.get_organization_data(organization_id=organization_id)
        now: datetime = datetime.now()
        months: list[str] = [
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

        pdf_bytes: bytes = await self.document_generator.generate_pdf(markdown_content=md_final)
        trabajador_nombre = form_data.get("trabajador_nombre") or form_data.get("cliente_nombre")
        cliente_nombre = trabajador_nombre or "cliente"
        base_name: str = template.name.replace(" ", "_").lower()
        cliente_seguro = cliente_nombre.replace(" ", "_").lower()
        timestamp = int(now.timestamp())
        generated_file_name = f"{base_name}_{cliente_seguro}_{timestamp}.pdf"
        service_items = form_data.get("service_items", []) if template.document_type == DocumentType.COMPANY else []
        start_date, end_date = self._resolve_generated_dates(form_data=form_data, now=now)
        document_payload: dict[str, int | str | bytes | Any | dict[str, Any | int | str]] = {
            "organization_id": organization_id,
            "template_id": template_id,
            "name": self._build_labor_contract_name(worker_name=trabajador_nombre),
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

        nuevo_documento = await self.document_adapter.save_generated_document(
            document_payload=document_payload,
            file=pdf_bytes,
            user_role=user_role,
        )

        return nuevo_documento

    async def get_template(
        self,
        template_id: int,
        organization_id: int,
        user_role: UserRole | None = None,
    ) -> TemplateTable | None:
        """Obtiene una plantilla de la organización."""
        template: TemplateTable | None = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        if template is None:
            return None
        if user_role in (None, UserRole.ADMIN):
            return template
        if not can_write_document_type(user_role=user_role, document_type=template.document_type):
            return None
        return template

    async def list_templates(self, organization_id: int, user_role: UserRole | None = None) -> Sequence[TemplateTable]:
        """Lista las plantillas de una organización."""
        templates: Sequence[TemplateTable] = await self.template_repo.list_by_organization(organization_id=organization_id)
        if user_role in (None, UserRole.ADMIN):
            return templates
        return [template for template in templates if can_write_document_type(user_role=user_role, document_type=template.document_type)]

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
