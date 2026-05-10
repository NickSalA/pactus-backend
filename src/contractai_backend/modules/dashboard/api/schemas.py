"""Schemas for dashboard API responses."""

from datetime import datetime

from pydantic import BaseModel, Field


class AreaChartYAxis(BaseModel):
    """Y axis metadata consumed by the frontend chart."""

    format: str = Field(default="currency")
    labels: list[float]


class AreaChartPoint(BaseModel):
    """One chart point for historical or forecast data."""

    x: str
    y: float
    is_forecast: bool = False


class AreaChartSeries(BaseModel):
    """One chart series."""

    name: str
    data: list[AreaChartPoint]


class AreaChartProps(BaseModel):
    """Chart props returned as a single payload."""

    title: str
    subtitle: str
    y_axis: AreaChartYAxis
    threshold_date: datetime
    series: list[AreaChartSeries]


class AreaChartResponse(BaseModel):
    """Response for area chart endpoints."""

    props: AreaChartProps


class AlertColor(BaseModel):
    """Visual colors for one alert bucket."""

    accent: str
    bg: str


class AlertItem(BaseModel):
    """Contract item displayed under an alert bucket."""

    id: int
    name: str
    detail: str | None = None
    status: str


class AlertCategory(BaseModel):
    """Alert bucket with count and a small preview list."""

    label: str
    color: AlertColor
    due_to: int | None = None
    count: int
    items: list[AlertItem]


class RecentContractResponse(BaseModel):
    """Recent contract card."""

    id: int
    title: str
    services: list[str]
    name: str
    dates: str


class TopCompanyResponse(BaseModel):
    """Top company ranking row."""

    name: str
    contracts: int
    amount: float


class TopServiceResponse(BaseModel):
    """Top service ranking row."""

    name: str
    quantity: int
    amount: float
