"""Dependency providers for audit APIs."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ....modules.audit.application.repositories import (
    AITokenUsageRepository,
    ChatbotActivityRepository,
    ContractActivityRepository,
    TemplateActivityRepository,
    UserActivityRepository,
)
from ....modules.audit.application.services import (
    AITokenTrackingService,
    ChatbotActivityService,
    ContractActivityService,
    TemplateActivityService,
    UserActivityService,
)
from ....modules.audit.composition import (
    build_ai_token_tracking_service,
    build_chatbot_activity_service,
    build_contract_activity_service,
    build_template_activity_service,
    build_user_activity_service,
)
from ....modules.audit.infrastructure import (
    SQLModelAITokenUsageRepository,
    SQLModelChatbotActivityRepository,
    SQLModelContractActivityRepository,
    SQLModelTemplateActivityRepository,
    SQLModelUserActivityRepository,
)
from ....shared.infrastructure.database import get_session


async def get_user_activity_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> UserActivityRepository:
    return SQLModelUserActivityRepository(session=session)


async def get_user_activity_service(
    repository: Annotated[UserActivityRepository, Depends(get_user_activity_repository)],
) -> UserActivityService:
    return build_user_activity_service(repository=repository)


async def get_chatbot_activity_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> ChatbotActivityRepository:
    return SQLModelChatbotActivityRepository(session=session)


async def get_chatbot_activity_service(
    repository: Annotated[ChatbotActivityRepository, Depends(get_chatbot_activity_repository)],
) -> ChatbotActivityService:
    return build_chatbot_activity_service(repository=repository)


async def get_template_activity_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TemplateActivityRepository:
    return SQLModelTemplateActivityRepository(session=session)


async def get_template_activity_service(
    repository: Annotated[TemplateActivityRepository, Depends(get_template_activity_repository)],
) -> TemplateActivityService:
    return build_template_activity_service(repository=repository)


async def get_contract_activity_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ContractActivityRepository:
    return SQLModelContractActivityRepository(session=session)


async def get_contract_activity_service(
    repository: Annotated[ContractActivityRepository, Depends(get_contract_activity_repository)],
) -> ContractActivityService:
    return build_contract_activity_service(repository=repository)


async def get_ai_token_usage_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AITokenUsageRepository:
    return SQLModelAITokenUsageRepository(session=session)


async def get_ai_token_tracking_service(
    repository: Annotated[AITokenUsageRepository, Depends(get_ai_token_usage_repository)],
) -> AITokenTrackingService:
    return build_ai_token_tracking_service(repository=repository)
