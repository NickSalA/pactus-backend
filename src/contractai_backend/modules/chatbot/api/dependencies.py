"""Este módulo define las dependencias para el chatbot, utilizando FastAPI's Depends para inyectar los servicios necesarios en los endpoints."""

from typing import Annotated

from fastapi import Depends, Request
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlmodel.ext.asyncio.session import AsyncSession

from ....modules.documents.application.services import ContractQueryService
from ....modules.documents.infrastructure import SQLModelDocumentRepository
from ....modules.users.domain.entities import UserTable
from ....shared.api.dependencies.security import get_current_user
from ....shared.config import settings
from ....shared.infrastructure.database import get_aclient, get_session
from ..application import ChatbotService, ConversationService, ILLMProvider
from ..infrastructure import ConversationRepository, QdrantVectorRepository
from ..infrastructure.agent import ContractAgentGraph, LangGraphGeminiAdapter, build_bc_tool, build_contracts_query_tool, get_llm


async def get_conversation_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ConversationService:
    """Construye el servicio de conversación, inyectando el repositorio necesario."""
    repo = ConversationRepository(session=session)
    return ConversationService(repository=repo)


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
    contract_repo = SQLModelDocumentRepository(session=session)
    contract_query_service = ContractQueryService(sql_repo=contract_repo)

    bc_tool = build_bc_tool(repo=vector_repo)
    contracts_query_tool = build_contracts_query_tool(service=contract_query_service, organization_id=current_user.organization_id)

    graph_builder = ContractAgentGraph(tools=[contracts_query_tool, bc_tool], llm=get_llm())
    compiled_graph = graph_builder.build_graph(checkpointer=checkpointer)

    return LangGraphGeminiAdapter(compiled_graph=compiled_graph)


async def get_chatbot_service(
    llm_provider: Annotated[ILLMProvider, Depends(get_llm_provider)], conv_service: Annotated[ConversationService, Depends(get_conversation_service)]
) -> ChatbotService:
    """Construye el servicio principal del chatbot, inyectando el LLM y el servicio de conversaciones."""
    return ChatbotService(llm_provider=llm_provider, conv_service=conv_service)
