"""Composition helpers for the folders module."""

from .application.repositories import FolderRepository
from .application.services import FolderService


def build_folder_service(repository: FolderRepository) -> FolderService:
    """Builds the folder application service."""
    return FolderService(sql_repo=repository)
