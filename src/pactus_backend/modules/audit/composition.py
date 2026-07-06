"""Composition helpers for audit services."""

from sqlmodel.ext.asyncio.session import AsyncSession

from ...modules.audit.application.repositories import (
    AITokenUsageRepository,
    ChatbotActivityRepository,
    ContractActivityRepository,
    TemplateActivityRepository,
    UserActivityRepository,
)
from ...modules.audit.application.services import (
    AITokenTrackingService,
    ChatbotActivityService,
    ContractActivityService,
    TemplateActivityService,
    UserActivityService,
)
from ...modules.audit.infrastructure import (
    SQLModelAITokenUsageRepository,
    SQLModelChatbotActivityRepository,
    SQLModelContractActivityRepository,
    SQLModelTemplateActivityRepository,
    SQLModelUserActivityRepository,
)


def build_user_activity_service(repository: UserActivityRepository) -> UserActivityService:
    return UserActivityService(repository=repository)


def build_chatbot_activity_service(repository: ChatbotActivityRepository) -> ChatbotActivityService:
    return ChatbotActivityService(repository=repository)


def build_default_user_activity_service(*, session: AsyncSession) -> UserActivityService:
    return build_user_activity_service(repository=SQLModelUserActivityRepository(session=session))


def build_default_chatbot_activity_service(*, session: AsyncSession) -> ChatbotActivityService:
    return build_chatbot_activity_service(repository=SQLModelChatbotActivityRepository(session=session))


def build_template_activity_service(repository: TemplateActivityRepository) -> TemplateActivityService:
    return TemplateActivityService(repository=repository)


def build_default_template_activity_service(*, session: AsyncSession) -> TemplateActivityService:
    return build_template_activity_service(repository=SQLModelTemplateActivityRepository(session=session))


def build_contract_activity_service(repository: ContractActivityRepository) -> ContractActivityService:
    return ContractActivityService(repository=repository)


def build_default_contract_activity_service(*, session: AsyncSession) -> ContractActivityService:
    return build_contract_activity_service(repository=SQLModelContractActivityRepository(session=session))


def build_ai_token_tracking_service(repository: AITokenUsageRepository) -> AITokenTrackingService:
    return AITokenTrackingService(repository=repository)


def build_default_ai_token_tracking_service(*, session: AsyncSession) -> AITokenTrackingService:
    return build_ai_token_tracking_service(repository=SQLModelAITokenUsageRepository(session=session))

