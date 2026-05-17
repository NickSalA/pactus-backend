"""Dependency injection for the folders module."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ....shared.infrastructure.database import get_session
from ..application.services import FolderService
from ..composition import build_folder_service
from ..infrastructure.postgres_repo import SQLModelFolderRepository


async def get_folder_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> SQLModelFolderRepository:
    """Provides a SQLModel implementation of the folder repository."""
    return SQLModelFolderRepository(session=session)


async def get_folder_service(
    repo: Annotated[SQLModelFolderRepository, Depends(get_folder_repository)]
) -> FolderService:
    """Provides an instance of the folder service."""
    return build_folder_service(repository=repo)
