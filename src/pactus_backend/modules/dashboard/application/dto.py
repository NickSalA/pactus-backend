"""Application DTOs for dashboard read models."""

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

    currency: str
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
    """Response for area chart use cases."""

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


class RetentionKPIs(BaseModel):
    """KPI metrics for worker retention."""

    active_retention_rate: float
    total_unique_workers: int
    avg_contracts_per_worker: float


class TenureDistributionPoint(BaseModel):
    """Distribution of workers by number of contracts."""

    contracts_count: int
    workers_count: int


class MonthlyRenewalPoint(BaseModel):
    """Aggregated renewal rate for one specific month."""

    month: str
    renewal_rate: float
    total_expired: int
    total_renewed: int


class WorkerRetentionDetail(BaseModel):
    """Metadata and history details for one specific worker."""

    worker_name: str
    worker_document_number: str | None
    contracts_count: int
    first_contract_start: str | None
    latest_contract_end: str | None


class RetentionDashboardResponse(BaseModel):
    """Complete response payload for the worker retention dashboard."""

    kpis: RetentionKPIs
    tenure_distribution: list[TenureDistributionPoint]
    renewal_trend: list[MonthlyRenewalPoint]
    details: list[WorkerRetentionDetail]


class OriginDistributionPoint(BaseModel):
    """Contract distribution by creation type or source."""

    origin_type: str
    count: int
    percentage: float


class ContractOriginResponse(BaseModel):
    """Complete response payload for the contract origin dashboard."""

    distribution: list[OriginDistributionPoint]
    total_contracts: int


class ClientLoyaltyKPIs(BaseModel):
    """KPI metrics for B2B client loyalty."""

    active_retention_rate: float
    total_unique_clients: int
    avg_contracts_per_client: float


class ClientTenureDistributionPoint(BaseModel):
    """Distribution of B2B clients by number of contracts."""

    contracts_count: int
    clients_count: int


class ClientMonthlyRenewalPoint(BaseModel):
    """Aggregated B2B client renewal rate for one specific month."""

    month: str
    renewal_rate: float
    total_expired: int
    total_renewed: int


class ClientLoyaltyDetail(BaseModel):
    """Metadata and history details for one specific B2B client."""

    client_name: str
    ruc: str | None
    contracts_count: int
    first_contract_start: str | None
    latest_contract_end: str | None


class CompanyLoyaltyDashboardResponse(BaseModel):
    """Complete response payload for the B2B client loyalty dashboard."""

    kpis: ClientLoyaltyKPIs
    tenure_distribution: list[ClientTenureDistributionPoint]
    renewal_trend: list[ClientMonthlyRenewalPoint]
    details: list[ClientLoyaltyDetail]
