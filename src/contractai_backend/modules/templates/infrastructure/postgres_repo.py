"""Repositorio de Plantillas utilizando SQLModel y AsyncSession para PostgreSQL."""

from collections.abc import Sequence

from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ....core.infrastructure.base import PostgresBaseRepository
from ...documents.domain import DocumentType
from ..application.repositories.base_relational import ITemplateFormatRepository, ITemplateRepository
from ..domain.entities import TemplateFormatTable, TemplateTable
from ..domain.formats import normalize_format_code
from ..domain.value_objs import TemplateState


class SQLModelTemplateRepository(PostgresBaseRepository[TemplateTable], ITemplateRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(model=TemplateTable, session=session)

    async def get_template_by_id(self, template_id: int, organization_id: int | None) -> TemplateTable | None:
        """Obtiene la plantilla validando que pertenezca a la organización."""
        query = select(self.model).where(self.model.id == template_id)
        if organization_id is not None:
            query = query.where(self.model.organization_id == organization_id)
        else:
            query = query.where(self.model.organization_id is None)
        result = await self.session.exec(statement=query)
        return result.first()

    async def list_by_organization(self, organization_id: int) -> Sequence[TemplateTable]:
        """Lista las plantillas de una organización."""
        query = select(self.model).where(self.model.organization_id == organization_id)
        result = await self.session.exec(statement=query)
        return result.all()

    async def publish(self, entity: TemplateTable) -> TemplateTable:
        """Publica una plantilla y archiva las publicadas previas del mismo formato."""
        db_merged = await self.session.merge(instance=entity)
        await self.session.exec(
            update(self.model)
            .where(
                self.model.organization_id == db_merged.organization_id,
                self.model.document_type == db_merged.document_type,
                self.model.template_format_id == db_merged.template_format_id,
                self.model.state == TemplateState.PUBLISHED,
                self.model.id != db_merged.id,
            )
            .values(state=TemplateState.ARCHIVED)
        )
        await self.session.commit()
        await self.session.refresh(instance=db_merged)
        return db_merged


class SQLModelTemplateFormatRepository(PostgresBaseRepository[TemplateFormatTable], ITemplateFormatRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(model=TemplateFormatTable, session=session)

    async def get_by_document_type_and_code(
        self,
        document_type: DocumentType,
        format_code: str,
    ) -> TemplateFormatTable | None:
        """Obtiene un formato activo por tipo documental y codigo."""
        normalized_format_code = normalize_format_code(format_code)
        query = select(self.model).where(
            self.model.document_type == document_type,
            self.model.format_code == normalized_format_code,
            self.model.is_active.is_(True),
        )
        result = await self.session.exec(statement=query)
        return result.first()

    async def list_active(self, document_type: DocumentType | None = None) -> Sequence[TemplateFormatTable]:
        """Lista formatos activos, opcionalmente filtrados por tipo documental."""
        query = select(self.model).where(self.model.is_active.is_(True))
        if document_type is not None:
            query = query.where(self.model.document_type == document_type)
        result = await self.session.exec(statement=query)
        return result.all()

    async def list_by_ids(self, ids: Sequence[int]) -> Sequence[TemplateFormatTable]:
        """Lista formatos por identificadores."""
        if not ids:
            return []
        query = select(self.model).where(self.model.id.in_(ids))
        result = await self.session.exec(statement=query)
        return result.all()
