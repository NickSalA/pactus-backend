"""Dependency injection for dashboard module."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ....shared.infrastructure.database import get_session
from ..application.repositories import DashboardRepository
from ..application.services import DashboardService
from ..infrastructure import SQLModelDashboardRepository


async def get_dashboard_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> DashboardRepository:
    """Provides the concrete dashboard repository."""
    return SQLModelDashboardRepository(session=session)


async def get_dashboard_service(repository: Annotated[DashboardRepository, Depends(get_dashboard_repository)]) -> DashboardService:
    """Provides the dashboard application service."""
    return DashboardService(repository=repository)
