"""Backward compatibility redirect bridge for dashboard repository."""

from .postgres.repository import SQLModelDashboardRepository

__all__: list[str] = ["SQLModelDashboardRepository"]
