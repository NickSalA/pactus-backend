"""Service layer for handling template-related operations, including contract generation based on templates and organization data."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from ...domain.entities import TemplateTable
from ..repositories.base_generate import IDocumentGenerator
from ..repositories.base_relational import IDocumentModuleAdapter, IOrganizationRepository, ITemplateRepository
from ..repositories.base_render import ITemplateRenderer


class TemplateService:
    def __init__(
        self,
        template_repo: ITemplateRepository,
        organization_repo: IOrganizationRepository,
        renderer: ITemplateRenderer,
        document_generator: IDocumentGenerator,
        document_adapter: IDocumentModuleAdapter,
    ):
        self.template_repo: ITemplateRepository = template_repo
        self.organization_repo: IOrganizationRepository = organization_repo
        self.renderer: ITemplateRenderer = renderer
        self.document_generator: IDocumentGenerator = document_generator
        self.document_adapter: IDocumentModuleAdapter = document_adapter

    async def generate_contract(self, template_id: int, organization_id: int, form_data: dict[str, Any]):
        """Genera un contrato a partir de una plantilla, los datos de la organización y los datos del formulario."""
        template: TemplateTable | None = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        if not template:
            raise ValueError("Template not found or does not belong to the organization.")
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
        cliente_nombre = form_data.get("trabajador_nombre") or form_data.get("cliente_nombre") or "cliente"
        base_name: str = template.name.replace(" ", "_").lower()
        cliente_seguro = cliente_nombre.replace(" ", "_").lower()
        timestamp = int(now.timestamp())
        generated_file_name = f"{base_name}_{cliente_seguro}_{timestamp}.pdf"
        document_payload: dict[str, int | str | bytes | Any | dict[str, Any | int | str]] = {
            "organization_id": organization_id,
            "template_id": template_id,
            "name": f"{template.name} - {cliente_nombre}",
            "client": cliente_nombre,
            "type": "SERVICES",
            "content": pdf_bytes,
            "start_date": form_data.get("contrato_fecha_inicio", now.date().isoformat()),
            "end_date": form_data.get("contrato_fecha_fin", now.date().isoformat()),
            "service_items": form_data.get("service_items", []),
            "form_data": master_dict,
            "file_name": generated_file_name,
        }

        nuevo_documento = await self.document_adapter.save_generated_document(document_payload=document_payload, file=pdf_bytes)

        return nuevo_documento

    async def get_template(self, template_id: int, organization_id: int) -> TemplateTable | None:
        """Obtiene los detalles de una plantilla asegurando que pertenezca a la organización."""
        template: TemplateTable | None = await self.template_repo.get_template_by_id(template_id=template_id, organization_id=organization_id)
        return template

    async def list_templates(self, organization_id: int) -> Sequence[TemplateTable]:
        """Lista todas las plantillas disponibles para una organización."""
        templates: Sequence[TemplateTable] = await self.template_repo.list_by_organization(organization_id=organization_id)
        return templates
