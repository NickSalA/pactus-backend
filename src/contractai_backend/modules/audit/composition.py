"""Composition helpers for audit services."""

from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.audit.application.repositories import UserActivityRepository
from contractai_backend.modules.audit.application.services import UserActivityService
from contractai_backend.modules.audit.infrastructure import SQLModelUserActivityRepository


def build_user_activity_service(repository: UserActivityRepository) -> UserActivityService:
    return UserActivityService(repository=repository)


def build_default_user_activity_service(*, session: AsyncSession) -> UserActivityService:
    return build_user_activity_service(repository=SQLModelUserActivityRepository(session=session))
