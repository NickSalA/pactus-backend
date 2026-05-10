"""Tests for dashboard routers with mocked dependencies."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.core.exceptions.base import AppError
from contractai_backend.modules.dashboard.api.dependencies import get_dashboard_service
from contractai_backend.modules.dashboard.api.routers import router
from contractai_backend.modules.dashboard.api.schemas import (
    AlertCategory,
    AlertColor,
    AreaChartProps,
    AreaChartResponse,
    AreaChartSeries,
    AreaChartYAxis,
    RecentContractResponse,
    TopCompanyResponse,
    TopServiceResponse,
)
from contractai_backend.shared.api.dependencies.security import get_current_user
from contractai_backend.shared.api.error_handlers import app_error_handler


def _make_app(mock_service) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/dashboard")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, organization_id=1)
    app.dependency_overrides[get_dashboard_service] = lambda: mock_service
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    return app


def _area_chart_response() -> AreaChartResponse:
    from datetime import UTC, datetime

    return AreaChartResponse(
        props=AreaChartProps(
            title="Ingresos Proyectados",
            subtitle="Historico vs. contratos asegurados a futuro",
            y_axis=AreaChartYAxis(labels=[0, 1000, 2000, 3000, 4000]),
            threshold_date=datetime(2026, 5, 1, tzinfo=UTC),
            series=[AreaChartSeries(name="Ingresos", data=[])],
        )
    )


class TestDashboardRouter:
    @pytest.mark.asyncio
    async def test_company_area_chart_returns_200(self):
        service = AsyncMock()
        service.get_area_chart.return_value = _area_chart_response()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/dashboard/area_chart/company")

        assert response.status_code == 200
        assert response.json()["props"]["title"] == "Ingresos Proyectados"

    @pytest.mark.asyncio
    async def test_labor_alert_center_returns_200(self):
        service = AsyncMock()
        service.get_alert_center.return_value = [
            AlertCategory(label="VENCEN PROXIMOS", color=AlertColor(accent="#000", bg="#fff"), due_to=30, count=0, items=[])
        ]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/dashboard/alert_center/labor")

        assert response.status_code == 200
        assert response.json()[0]["due_to"] == 30

    @pytest.mark.asyncio
    async def test_recent_contracts_returns_200(self):
        service = AsyncMock()
        service.get_recent_contracts.return_value = [
            RecentContractResponse(id=201, title="Contrato", services=["Cloud"], name="TechCorp", dates="05/15/26 - 05/15/27")
        ]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/dashboard/recent_contracts/company")

        assert response.status_code == 200
        assert response.json()[0]["id"] == 201

    @pytest.mark.asyncio
    async def test_top_rankings_return_200(self):
        service = AsyncMock()
        service.get_top_companies.return_value = [TopCompanyResponse(name="TechCorp SA", contracts=5, amount=120000)]
        service.get_top_services.return_value = [TopServiceResponse(name="Cloud Support", quantity=5, amount=60000)]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            companies_response = await client.get("/dashboard/top_companies")
            services_response = await client.get("/dashboard/top_services")

        assert companies_response.status_code == 200
        assert services_response.status_code == 200
        assert companies_response.json()[0]["contracts"] == 5
        assert services_response.json()[0]["quantity"] == 5
