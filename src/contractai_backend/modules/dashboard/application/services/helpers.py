"""Shared helper utilities and protocol definitions for dashboard application services."""

from datetime import date
from math import ceil
from typing import Protocol

from ..repositories import DashboardRepository

AREA_CHART_HISTORY_MONTHS = 4
AREA_CHART_FORECAST_MONTHS = 2
ALERT_PREVIEW_LIMIT = 3
RECENT_CONTRACTS_LIMIT = 4
TOP_RANKING_LIMIT = 5
MONTH_LABELS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


class DashboardServiceProtocol(Protocol):
    """Protocol defining the structural interface required by dashboard service mixins."""

    repository: DashboardRepository

    @staticmethod
    def _add_months(value: date, months: int) -> date: ...

    @staticmethod
    def _month_start(value: date) -> date: ...

    @staticmethod
    def _format_date_range(start_date: date | None, end_date: date | None) -> str: ...

    @staticmethod
    def _build_y_axis_labels(max_value: float) -> list[float]: ...


class DashboardServiceHelpers:
    """Shared calculation and formatting helper methods for dashboard services."""

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        return date(year, month, 1)

    @staticmethod
    def _month_start(value: date) -> date:
        return date(value.year, value.month, 1)

    @staticmethod
    def _format_date_range(start_date: date | None, end_date: date | None) -> str:
        if start_date is None or end_date is None:
            return "Sin fechas"
        return f"{start_date.strftime('%m/%d/%y')} - {end_date.strftime('%m/%d/%y')}"

    @staticmethod
    def _build_y_axis_labels(max_value: float) -> list[float]:
        if max_value <= 0:
            return [0.0, 20.0, 40.0, 60.0, 80.0]

        step = max(1, ceil(max_value / 4 / 1000) * 1000)
        return [float(step * index) for index in range(5)]
