"""Definición de la interfaz del repositorio de plantillas."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from .....core.application.base import BaseRepository
from ....users.domain.value_objs import UserRole
from ...domain.entities import TemplateTable


class ITemplateRepository(BaseRepository[TemplateTable]):
    @abstractmethod
    async def get_template_by_id(self, template_id: int, organization_id: int | None) -> TemplateTable | None:
        """Obtiene la plantilla validando que pertenezca a la organización."""
        pass

    @abstractmethod
    async def list_by_organization(self, organization_id: int) -> Sequence[TemplateTable]:
        """Lista las plantillas de una organización."""
        pass


class IOrganizationRepository(ABC):
    @abstractmethod
    async def get_organization_data(self, organization_id: int) -> dict[str, Any]:
        """Obtiene los datos de la organización."""
        pass


class IDocumentModuleAdapter(ABC):
    @abstractmethod
    async def save_generated_document(self, document_payload: dict, file: bytes, user_role: UserRole | None) -> Any:
        """Envía los datos del PDF generado al módulo de Documentos para que él lo guarde."""
        pass
