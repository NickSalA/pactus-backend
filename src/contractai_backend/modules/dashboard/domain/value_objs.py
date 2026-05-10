"""Dashboard value objects."""

from enum import StrEnum


class DashboardContractScope(StrEnum):
    """Supported dashboard contract scopes exposed by the API."""

    COMPANY = "company"
    LABOR = "labor"
