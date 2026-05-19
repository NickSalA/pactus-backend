"""Módulo de dependencias para el API de plantillas."""

from typing import Annotated

import httpx
from fastapi import Depends
from qdrant_client import AsyncQdrantClient, QdrantClient
from sqlmodel.ext.asyncio.session import AsyncSession

from ....shared.infrastructure.database import get_aclient, get_client, get_session
from ....shared.infrastructure.http import get_http_client
from ...documents.application.repositories import DocumentExtractor
from ...documents.application.services import DocumentCommandService
from ...documents.composition import build_default_document_command_service, build_default_document_extractor
from ...organizations.application.services.organization_service import OrganizationService
from ...organizations.composition import build_organization_service
from ...organizations.infrastructure.postgres_repo import SQLModelOrganizationRepository
from ..application.repositories import (
    IDocumentGenerator,
    IDocumentModuleAdapter,
    IOrganizationRepository,
    ITemplateDraftGenerator,
    ITemplateFormatRepository,
    ITemplateRenderer,
    ITemplateRepository,
)
from ..application.services.template_authoring_service import TemplateAuthoringService
from ..application.services.template_service import TemplateService
from ..infrastructure import (
    DocumentModuleAdapter,
    GeminiTemplateDraftGenerator,
    JinjaRenderer,
    OrganizationModuleAdapter,
    SQLModelTemplateFormatRepository,
    SQLModelTemplateRepository,
    WeasyPrintGenerator,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AsyncQdrantDep = Annotated[AsyncQdrantClient, Depends(get_aclient)]
SyncQdrantDep = Annotated[QdrantClient, Depends(get_client)]


async def get_template_repository(session: SessionDep) -> ITemplateRepository:
    """Devuelve una instancia del repositorio de plantillas."""
    return SQLModelTemplateRepository(session=session)


async def get_template_format_repository(session: SessionDep) -> ITemplateFormatRepository:
    """Devuelve una instancia del repositorio de formatos de plantilla."""
    return SQLModelTemplateFormatRepository(session=session)


async def get_document_command_service(
    session: SessionDep,
    async_qdrant: AsyncQdrantDep,
    sync_qdrant: SyncQdrantDep,
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> DocumentCommandService:
    """Builds the document service needed by template generation."""
    return build_default_document_command_service(session=session, async_qdrant=async_qdrant, sync_qdrant=sync_qdrant, http_client=client)


async def get_organization_service(session: SessionDep) -> OrganizationService:
    """Builds the organization service needed by template rendering."""
    return build_organization_service(repository=SQLModelOrganizationRepository(session=session))


DocumentServiceDep = Annotated[DocumentCommandService, Depends(get_document_command_service)]
OrganizationDep = Annotated[OrganizationService, Depends(get_organization_service)]


async def get_document_module_adapter(doc_service: DocumentServiceDep) -> IDocumentModuleAdapter:
    """Devuelve una instancia del adaptador del módulo de documentos."""
    return DocumentModuleAdapter(doc_service=doc_service)


async def get_organization_repository(org_service: OrganizationDep) -> IOrganizationRepository:
    """Devuelve una instancia del repositorio de organizaciones."""
    return OrganizationModuleAdapter(org_service=org_service)


async def get_template_renderer() -> ITemplateRenderer:
    """Devuelve una instancia del renderizador de plantillas."""
    return JinjaRenderer()


async def get_document_generator() -> IDocumentGenerator:
    """Devuelve una instancia del generador de documentos."""
    return WeasyPrintGenerator()


async def get_document_extractor() -> DocumentExtractor:
    """Devuelve una instancia del extractor de documentos."""
    return build_default_document_extractor()


async def get_template_draft_generator() -> ITemplateDraftGenerator:
    """Devuelve una instancia del generador de borradores de plantillas."""
    return GeminiTemplateDraftGenerator()


TemplateRepositoryDep = Annotated[ITemplateRepository, Depends(get_template_repository)]
TemplateFormatRepositoryDep = Annotated[ITemplateFormatRepository, Depends(get_template_format_repository)]
DocumentAdapterDep = Annotated[IDocumentModuleAdapter, Depends(get_document_module_adapter)]
OrganizationRepositoryDep = Annotated[IOrganizationRepository, Depends(get_organization_repository)]
TemplateRendererDep = Annotated[ITemplateRenderer, Depends(get_template_renderer)]
DocumentGeneratorDep = Annotated[IDocumentGenerator, Depends(get_document_generator)]
DocumentExtractorDep = Annotated[DocumentExtractor, Depends(get_document_extractor)]
TemplateDraftGeneratorDep = Annotated[ITemplateDraftGenerator, Depends(get_template_draft_generator)]


async def get_template_service(
    template_repo: TemplateRepositoryDep,
    template_format_repo: TemplateFormatRepositoryDep,
    document_adapter: DocumentAdapterDep,
    organization_repo: OrganizationRepositoryDep,
    renderer: TemplateRendererDep,
    generator: DocumentGeneratorDep,
) -> TemplateService:
    """Devuelve una instancia del servicio de plantillas."""
    return TemplateService(
        template_repo=template_repo,
        template_format_repo=template_format_repo,
        document_adapter=document_adapter,
        organization_repo=organization_repo,
        renderer=renderer,
        document_generator=generator,
    )


async def get_template_authoring_service(
    template_repo: TemplateRepositoryDep,
    template_format_repo: TemplateFormatRepositoryDep,
    organization_repo: OrganizationRepositoryDep,
    renderer: TemplateRendererDep,
    extractor: DocumentExtractorDep,
    draft_generator: TemplateDraftGeneratorDep,
) -> TemplateAuthoringService:
    """Devuelve una instancia del servicio de autoría de plantillas."""
    return TemplateAuthoringService(
        template_repo=template_repo,
        template_format_repo=template_format_repo,
        organization_repo=organization_repo,
        renderer=renderer,
        extractor=extractor,
        draft_generator=draft_generator,
    )
