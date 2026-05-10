"""HTTP endpoints for dashboard analytics."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends

from ....shared.api.dependencies.security import CurrentUserDep
from ...documents.domain.value_objs import DocumentType
from ..application.services import DashboardService
from .dependencies import get_dashboard_service
from .schemas import AlertCategory, AreaChartResponse, RecentContractResponse, TopCompanyResponse, TopServiceResponse

router = APIRouter()

DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]


@router.get(path="/area_chart/company", response_model=AreaChartResponse)
async def get_company_area_chart(service: DashboardServiceDep, current_user: CurrentUserDep) -> AreaChartResponse:
    """Returns the company contracts area chart for managers."""
    return await service.get_area_chart(current_user=current_user, document_type=DocumentType.COMPANY)


@router.get(path="/area_chart/labor", response_model=AreaChartResponse)
async def get_labor_area_chart(service: DashboardServiceDep, current_user: CurrentUserDep) -> AreaChartResponse:
    """Returns the labor contracts area chart for HR users."""
    return await service.get_area_chart(current_user=current_user, document_type=DocumentType.LABOR)


@router.get(path="/alert_center/company", response_model=list[AlertCategory])
async def get_company_alert_center(service: DashboardServiceDep, current_user: CurrentUserDep) -> list[AlertCategory]:
    """Returns company contract alert buckets for managers."""
    return await service.get_alert_center(current_user=current_user, document_type=DocumentType.COMPANY)


@router.get(path="/alert_center/labor", response_model=list[AlertCategory])
async def get_labor_alert_center(service: DashboardServiceDep, current_user: CurrentUserDep) -> list[AlertCategory]:
    """Returns labor contract alert buckets for HR users."""
    return await service.get_alert_center(current_user=current_user, document_type=DocumentType.LABOR)


@router.get(path="/recent_contracts/company", response_model=Sequence[RecentContractResponse])
async def get_company_recent_contracts(service: DashboardServiceDep, current_user: CurrentUserDep) -> Sequence[RecentContractResponse]:
    """Returns recently updated company contracts for managers."""
    return await service.get_recent_contracts(current_user=current_user, document_type=DocumentType.COMPANY)


@router.get(path="/recent_contracts/labor", response_model=Sequence[RecentContractResponse])
async def get_labor_recent_contracts(service: DashboardServiceDep, current_user: CurrentUserDep) -> Sequence[RecentContractResponse]:
    """Returns recently updated labor contracts for HR users."""
    return await service.get_recent_contracts(current_user=current_user, document_type=DocumentType.LABOR)


@router.get(path="/top_companies", response_model=Sequence[TopCompanyResponse])
async def get_top_companies(service: DashboardServiceDep, current_user: CurrentUserDep) -> Sequence[TopCompanyResponse]:
    """Returns top company counterparties for managers."""
    return await service.get_top_companies(current_user=current_user)


@router.get(path="/top_services", response_model=Sequence[TopServiceResponse])
async def get_top_services(service: DashboardServiceDep, current_user: CurrentUserDep) -> Sequence[TopServiceResponse]:
    """Returns top company services for managers."""
    return await service.get_top_services(current_user=current_user)
