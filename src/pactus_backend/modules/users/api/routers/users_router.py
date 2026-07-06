"""Router de usuarios."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from .....modules.billing.api.dependencies import get_paypal_subscription_service
from .....modules.billing.application.services import PayPalSubscriptionService
from .....modules.users.api.dependencies import get_user_application_service
from .....modules.users.api.schemas import CurrentUserResponse, UserResponse
from .....modules.users.application.dto.user_request import UserUpdateRequest
from .....modules.users.application.services.user_service import UserService
from .....shared.api.dependencies.security import CurrentUserDep

router = APIRouter()


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    current_user: CurrentUserDep,
    subscription_service: Annotated[PayPalSubscriptionService, Depends(get_paypal_subscription_service)],
) -> CurrentUserResponse:
    """Endpoint para obtener los datos del usuario autenticado."""
    subscription_active = await subscription_service.check_subscription_active(current_user.organization_id)
    return CurrentUserResponse(
        **current_user.model_dump(),
        subscription_active=subscription_active,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    request: UserUpdateRequest,
    user_service: Annotated[UserService, Depends(get_user_application_service)],
    current_user: CurrentUserDep,
) -> UserResponse:
    """Endpoint para actualizar el rol de un usuario."""
    updated_user = await user_service.update_user(user_id, request, actor=current_user)
    return UserResponse.model_validate(updated_user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    user_service: Annotated[UserService, Depends(get_user_application_service)],
    current_user: CurrentUserDep,
) -> None:
    """Endpoint para hacer soft delete de un usuario."""
    await user_service.soft_delete_user(user_id, actor=current_user)
