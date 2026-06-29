"""Adaptador que conecta el módulo de templates con el servicio de organizaciones para obtener datos necesarios durante el renderizado."""

from typing import Any

from ....modules.organizations.domain.entities import OrganizationTable
from ...organizations.application.services.organization_service import OrganizationService
from ..application.repositories.base_relational import IOrganizationRepository


class OrganizationModuleAdapter(IOrganizationRepository):
    def __init__(self, org_service: OrganizationService):
        self.org_service: OrganizationService = org_service

    async def get_organization_data(self, organization_id: int) -> dict[str, Any]:
        """Obtiene los datos de la organización necesarios para el renderizado de plantillas."""
        org_entity: OrganizationTable = await self.org_service.get_organization(organization_id=organization_id)
        if not org_entity:
            raise ValueError("Organization not found.")
        return {
            "empleador_razon_social": org_entity.name,
            "empleador_ruc": org_entity.ruc,
            "empleador_domicilio": org_entity.address,
            "empleador_descripcion": org_entity.company_type,
            "empleador_objeto_social": org_entity.objeto_social,
            "representante_nombre": org_entity.legal_rep_name,
            "representante_dni": org_entity.legal_rep_dni,
            "jurisdiccion": org_entity.jurisdiction,
            "lugar_firma": org_entity.city,
            "autorizacion_entidad": org_entity.autorizacion_entidad,
            "autorizacion_fecha": org_entity.autorizacion_fecha.isoformat() if org_entity.autorizacion_fecha else None,
            "autorizacion_emitida_por": org_entity.autorizacion_emitida_por,
            "empleador_email": org_entity.email,
            "empleador_telefono": org_entity.phone,
        }
