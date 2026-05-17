"""API routers for the folders module."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from ....shared.api.dependencies.security import CurrentUserDep
from ..application.services import FolderService
from .dependencies import get_folder_service
from .schemas import FolderCreateRequest, FolderResponse, FolderUpdateRequest

router = APIRouter()


@router.get(path="/", response_model=Sequence[FolderResponse])
async def list_folders(
    service: Annotated[FolderService, Depends(get_folder_service)],
    current_user: CurrentUserDep,
) -> Sequence[FolderResponse]:
    """Endpoint to list folders visible to the current user."""
    folders = await service.list_folders(current_user=current_user)
    return [FolderResponse.model_validate(folder) for folder in folders]


@router.post(path="/", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    payload: FolderCreateRequest,
    service: Annotated[FolderService, Depends(get_folder_service)],
    current_user: CurrentUserDep,
) -> FolderResponse:
    """Endpoint to create a folder in the current role scope."""
    folder = await service.create_folder(current_user=current_user, data=payload)
    return FolderResponse.model_validate(folder)


@router.patch(path="/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: int,
    payload: FolderUpdateRequest,
    service: Annotated[FolderService, Depends(get_folder_service)],
    current_user: CurrentUserDep,
) -> FolderResponse:
    """Endpoint to update a folder."""
    folder = await service.update_folder(current_user=current_user, folder_id=folder_id, data=payload)
    return FolderResponse.model_validate(folder)


@router.delete(path="/{folder_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_folder(
    folder_id: int,
    service: Annotated[FolderService, Depends(get_folder_service)],
    current_user: CurrentUserDep,
) -> None:
    """Endpoint to delete a folder."""
    await service.delete_folder(current_user=current_user, folder_id=folder_id)
