"""Definición de la interfaz del repositorio de plantillas."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from .....core.application.base import BaseRepository
from ....documents.domain import DocumentType
from ....users.domain.value_objs import UserRole
from ...domain.entities import TemplateFormatTable, TemplateTable


class ITemplateRepository(BaseRepository[TemplateTable]):
    @abstractmethod
    async def get_template_by_id(self, template_id: int, organization_id: int | None) -> TemplateTable | None:
        """Obtiene la plantilla validando que pertenezca a la organización."""
        pass

    @abstractmethod
    async def list_by_organization(self, organization_id: int) -> Sequence[TemplateTable]:
        """Lista las plantillas de una organización."""
        pass

    @abstractmethod
    async def publish(self, entity: TemplateTable) -> TemplateTable:
        """Publica una plantilla y archiva las publicadas previas del mismo formato."""
        pass


class ITemplateFormatRepository(BaseRepository[TemplateFormatTable]):
    @abstractmethod
    async def get_by_document_type_and_code(
        self,
        document_type: DocumentType,
        format_code: str,
    ) -> TemplateFormatTable | None:
        """Obtiene un formato activo por tipo documental y codigo."""
        pass

    @abstractmethod
    async def list_active(self, document_type: DocumentType | None = None) -> Sequence[TemplateFormatTable]:
        """Lista formatos activos, opcionalmente filtrados por tipo documental."""
        pass

    @abstractmethod
    async def list_by_ids(self, ids: Sequence[int]) -> Sequence[TemplateFormatTable]:
        """Lista formatos por identificadores."""
        pass


class IOrganizationRepository(ABC):
    @abstractmethod
    async def get_organization_data(self, organization_id: int) -> dict[str, Any]:
        """Obtiene los datos de la organización."""
        pass


class IDocumentModuleAdapter(ABC):
    @abstractmethod
    async def save_generated_document(self, document_payload: dict, file: bytes, user_role: UserRole | None, actor: Any | None = None) -> Any:
        pass
