"""Composition helpers for audit services."""

from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.audit.application.repositories import ChatbotActivityRepository, UserActivityRepository
from contractai_backend.modules.audit.application.services import ChatbotActivityService, UserActivityService
from contractai_backend.modules.audit.infrastructure import SQLModelChatbotActivityRepository, SQLModelUserActivityRepository


def build_user_activity_service(repository: UserActivityRepository) -> UserActivityService:
    return UserActivityService(repository=repository)


def build_chatbot_activity_service(repository: ChatbotActivityRepository) -> ChatbotActivityService:
    return ChatbotActivityService(repository=repository)


def build_default_user_activity_service(*, session: AsyncSession) -> UserActivityService:
    return build_user_activity_service(repository=SQLModelUserActivityRepository(session=session))


def build_default_chatbot_activity_service(*, session: AsyncSession) -> ChatbotActivityService:
    return build_chatbot_activity_service(repository=SQLModelChatbotActivityRepository(session=session))
