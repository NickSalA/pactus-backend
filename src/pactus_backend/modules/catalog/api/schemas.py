"""HTTP schemas for catalog module API requests and responses."""

from ..application.dto import (
    ServiceCreateRequest as ApplicationServiceCreateRequest,
)
from ..application.dto import (
    ServiceResponse as ApplicationServiceResponse,
)
from ..application.dto import (
    ServiceUpdateRequest as ApplicationServiceUpdateRequest,
)


class ServiceCreateRequest(ApplicationServiceCreateRequest):
    """HTTP request body for creating a catalog service."""


class ServiceUpdateRequest(ApplicationServiceUpdateRequest):
    """HTTP request body for updating a catalog service."""


class ServiceResponse(ApplicationServiceResponse):
    """HTTP response body for catalog services."""

__all__ = ["ServiceCreateRequest", "ServiceResponse", "ServiceUpdateRequest"]
