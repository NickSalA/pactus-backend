"""Este módulo define las dependencias para el chatbot, utilizando FastAPI's Depends para inyectar los servicios necesarios en los endpoints."""

from typing import Annotated

from fastapi import Depends, Request
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlmodel.ext.asyncio.session import AsyncSession

from ....modules.audit.application.services import ChatbotActivityService
from ....modules.audit.composition import build_default_chatbot_activity_service
from ....modules.catalog.composition import build_default_service_repository
from ....modules.dashboard.application.services import DashboardService
from ....modules.dashboard.infrastructure import SQLModelDashboardRepository
from ....modules.documents.application.services import ContractQueryService
from ....modules.documents.composition import build_default_document_repository
from ....modules.documents.domain.access_policy import can_read_document_type, get_readable_document_types
from ....modules.documents.domain.value_objs import DocumentState, DocumentType
from ....modules.users.domain.entities import UserTable
from ....shared.api.dependencies.security import get_current_user
from ....shared.config import settings
from ....shared.infrastructure.database import get_aclient, get_session
from ..application import ChatbotService, ConversationService, ILLMProvider, TokenUsageService
from ..composition import build_conversation_service
from ..infrastructure import ConversationRepository, QdrantVectorRepository, TokenUsageRepository
from ..infrastructure.agent import (
    ContractAgentGraph,
    LangGraphLLMAdapter,
    build_bc_tool,
    build_company_contracts_query_tool,
    build_dashboard_chart_tool,
    build_labor_contracts_query_tool,
    build_party_lookup_tool,
    get_llm,
)


async def get_conversation_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ConversationService:
    """Construye el servicio de conversación, inyectando el repositorio necesario."""
    repo = ConversationRepository(session=session)
    return build_conversation_service(repository=repo)


async def get_token_usage_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> TokenUsageRepository:
    """Construye el repositorio de token usage."""
    return TokenUsageRepository(session=session)


async def get_token_usage_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenUsageService:
    """Construye el servicio de token usage."""
    usage_repo = TokenUsageRepository(session=session)
    conv_repo = ConversationRepository(session=session)
    return TokenUsageService(usage_repo=usage_repo, conv_repo=conv_repo)


async def get_llm_provider(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[UserTable, Depends(get_current_user)],
) -> ILLMProvider:
    """Extrae el pool del estado de la app y construye el adaptador LLM."""
    pool = request.app.state.pool
    checkpointer = AsyncPostgresSaver(conn=pool)

    vector_repo: QdrantVectorRepository = await QdrantVectorRepository.build(
        collection_names=[settings.INDEX_NAME, settings.DRIVE_INDEX_NAME],
        client=await get_aclient(),
        organization_id=current_user.organization_id,
    )
    contract_repo = build_default_document_repository(session=session)
    service_catalog_repo = build_default_service_repository(session=session)
    contract_query_service = ContractQueryService(sql_repo=contract_repo, service_repo=service_catalog_repo)
    readable_document_types = get_readable_document_types(current_user.role)
    document_filters = {"organization_id": current_user.organization_id}
    documents = await contract_repo.get_all(filters=document_filters)
    document_ids = [document.id for document in documents if document.id is not None]
    document_kinds = await contract_repo.get_contract_kinds_by_document_ids(document_ids=document_ids)

    documents_with_children = [document for document in documents if document.id is not None and document_kinds.get(document.id) is not None]

    if readable_document_types is not None:
        documents_with_children = [doc for doc in documents_with_children if DocumentType(document_kinds[doc.id]) in readable_document_types]

    visible_documents = [doc for doc in documents_with_children if ContractQueryService.is_chatbot_visible_contract(doc)]

    default_document_ids = {document.id for document in visible_documents if document.id is not None}
    document_ids_by_state: dict[DocumentState, set[int]] = {}
    for document in visible_documents:
        if document.id is not None and document.state is not None:
            document_ids_by_state.setdefault(DocumentState(document.state), set()).add(document.id)

    bc_tool = build_bc_tool(
        repo=vector_repo,
        user_role=current_user.role,
        allowed_document_ids=default_document_ids,
        document_ids_by_state=document_ids_by_state,
    )
    party_lookup_tool = build_party_lookup_tool(repo=contract_repo, organization_id=current_user.organization_id)

    agent_tools = [bc_tool]

    # Inyectar tools condicionalmente usando las políticas de dominio (access_policy.py)
    if can_read_document_type(current_user.role, DocumentType.COMPANY):
        agent_tools.append(
            build_company_contracts_query_tool(
                service=contract_query_service,
                organization_id=current_user.organization_id,
            )
        )

    if can_read_document_type(current_user.role, DocumentType.LABOR):
        agent_tools.append(
            build_labor_contracts_query_tool(
                service=contract_query_service,
                organization_id=current_user.organization_id,
            )
        )

    dashboard_repo = SQLModelDashboardRepository(session=session)
    dashboard_service = DashboardService(repository=dashboard_repo)
    agent_tools.append(
        build_dashboard_chart_tool(
            service=dashboard_service,
            user=current_user,
        )
    )

    graph_builder = ContractAgentGraph(
        tools=agent_tools,
        permission_tools=[party_lookup_tool],
        llm=get_llm(),
    )
    compiled_graph = graph_builder.build_graph(checkpointer=checkpointer)

    return LangGraphLLMAdapter(compiled_graph=compiled_graph)


async def get_chatbot_service(
    llm_provider: Annotated[ILLMProvider, Depends(get_llm_provider)],
    conv_service: Annotated[ConversationService, Depends(get_conversation_service)],
    token_usage_repo: Annotated[TokenUsageRepository, Depends(get_token_usage_repository)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatbotService:
    """Construye el servicio principal del chatbot, inyectando el LLM y el servicio de conversaciones."""
    chatbot_activity_service: ChatbotActivityService = build_default_chatbot_activity_service(session=session)
    return ChatbotService(
        llm_provider=llm_provider,
        conv_service=conv_service,
        token_usage_repo=token_usage_repo,
        chatbot_activity_service=chatbot_activity_service,
    )
