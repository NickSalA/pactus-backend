"""API schemas for organizations."""

from ..application.dto import (
    OrganizationCreateRequest as ApplicationOrganizationCreateRequest,
)
from ..application.dto import (
    OrganizationMemberCreateRequest as ApplicationOrganizationMemberCreateRequest,
)
from ..application.dto import (
    OrganizationMemberNotificationsUpdateRequest as ApplicationOrganizationMemberNotificationsUpdateRequest,
)
from ..application.dto import (
    OrganizationMemberResponse as ApplicationOrganizationMemberResponse,
)
from ..application.dto import (
    OrganizationMemberRoleUpdateRequest as ApplicationOrganizationMemberRoleUpdateRequest,
)
from ..application.dto import (
    OrganizationResponse as ApplicationOrganizationResponse,
)
from ..application.dto import (
    OrganizationUpdateRequest as ApplicationOrganizationUpdateRequest,
)


class OrganizationCreateRequest(ApplicationOrganizationCreateRequest):
    """HTTP request body for creating an organization."""


class OrganizationUpdateRequest(ApplicationOrganizationUpdateRequest):
    """HTTP request body for updating an organization."""


class OrganizationResponse(ApplicationOrganizationResponse):
    """HTTP response schema for an organization."""


class OrganizationMemberCreateRequest(ApplicationOrganizationMemberCreateRequest):
    """HTTP request body for creating a member."""


class OrganizationMemberRoleUpdateRequest(ApplicationOrganizationMemberRoleUpdateRequest):
    """HTTP request body for updating a member's role."""


class OrganizationMemberNotificationsUpdateRequest(ApplicationOrganizationMemberNotificationsUpdateRequest):
    """HTTP request body for updating a member's notifications."""


class OrganizationMemberResponse(ApplicationOrganizationMemberResponse):
    """HTTP response schema for organization members."""

__all__ = [
    "OrganizationCreateRequest",
    "OrganizationMemberCreateRequest",
    "OrganizationMemberNotificationsUpdateRequest",
    "OrganizationMemberResponse",
    "OrganizationMemberRoleUpdateRequest",
    "OrganizationResponse",
    "OrganizationUpdateRequest",
]
