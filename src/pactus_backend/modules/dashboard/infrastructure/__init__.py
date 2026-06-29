"""Infrastructure package for dashboard adapters."""

from .postgres.repository import SQLModelDashboardRepository

__all__ = ["SQLModelDashboardRepository"]
