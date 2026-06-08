"""Router de usuarios."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from contractai_backend.modules.users.api.dependencies import get_user_application_service
from contractai_backend.modules.users.api.schemas import CurrentUserResponse, UserResponse
from contractai_backend.modules.users.application.dto.user_request import UserUpdateRequest
from contractai_backend.modules.users.application.services.user_service import UserService

from .....shared.api.dependencies.security import CurrentUserDep

router = APIRouter()


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(current_user: CurrentUserDep) -> CurrentUserResponse:
    """Endpoint para obtener los datos del usuario autenticado."""
    return CurrentUserResponse.model_validate(current_user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    request: UserUpdateRequest,
    user_service: Annotated[UserService, Depends(get_user_application_service)],
    _current_user: CurrentUserDep,
) -> UserResponse:
    """Endpoint para actualizar los datos de un usuario."""
    updated_user = await user_service.update_user(user_id, request)
    return UserResponse.model_validate(updated_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    user_service: Annotated[UserService, Depends(get_user_application_service)],
    _current_user: CurrentUserDep,
) -> None:
    """Endpoint para hacer soft delete de un usuario."""
    await user_service.soft_delete_user(user_id)

