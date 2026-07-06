"""HTTP schemas for users."""

from ..application.dto import CurrentUserResponse as ApplicationCurrentUserResponse
from ..application.dto import UserResponse as ApplicationUserResponse


class UserResponse(ApplicationUserResponse):
    """HTTP response body for users."""


class CurrentUserResponse(ApplicationCurrentUserResponse):
    """HTTP response body for the authenticated user."""

__all__ = ["CurrentUserResponse", "UserResponse"]
