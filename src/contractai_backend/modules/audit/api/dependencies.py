"""Dependency providers for audit APIs."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.audit.application.repositories import UserActivityRepository
from contractai_backend.modules.audit.application.services import UserActivityService
from contractai_backend.modules.audit.composition import build_user_activity_service
from contractai_backend.modules.audit.infrastructure import SQLModelUserActivityRepository
from contractai_backend.shared.infrastructure.database import get_session


async def get_user_activity_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> UserActivityRepository:
    return SQLModelUserActivityRepository(session=session)


async def get_user_activity_service(
    repository: Annotated[UserActivityRepository, Depends(get_user_activity_repository)],
) -> UserActivityService:
    return build_user_activity_service(repository=repository)
