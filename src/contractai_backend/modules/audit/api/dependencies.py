"""Dependency providers for audit APIs."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.audit.application.repositories import (
    ChatbotActivityRepository,
    TemplateActivityRepository,
    UserActivityRepository,
)
from contractai_backend.modules.audit.application.services import (
    ChatbotActivityService,
    TemplateActivityService,
    UserActivityService,
)
from contractai_backend.modules.audit.composition import (
    build_chatbot_activity_service,
    build_template_activity_service,
    build_user_activity_service,
)
from contractai_backend.modules.audit.infrastructure import (
    SQLModelChatbotActivityRepository,
    SQLModelTemplateActivityRepository,
    SQLModelUserActivityRepository,
)
from contractai_backend.shared.infrastructure.database import get_session


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
