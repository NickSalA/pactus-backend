"""HTTP schemas for folders module API requests and responses."""

from ..application.dto import (
    FolderCreateRequest as ApplicationFolderCreateRequest,
)
from ..application.dto import (
    FolderResponse as ApplicationFolderResponse,
)
from ..application.dto import (
    FolderUpdateRequest as ApplicationFolderUpdateRequest,
)


class FolderCreateRequest(ApplicationFolderCreateRequest):
    """HTTP request body for creating a folder."""


class FolderUpdateRequest(ApplicationFolderUpdateRequest):
    """HTTP request body for updating a folder."""


class FolderResponse(ApplicationFolderResponse):
    """HTTP response body for folders."""

__all__ = ["FolderCreateRequest", "FolderResponse", "FolderUpdateRequest"]
