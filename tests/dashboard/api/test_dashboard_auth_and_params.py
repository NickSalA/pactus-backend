"""Tests for dashboard auth errors and query parameters."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.core.exceptions.base import AppError, ForbiddenError
from contractai_backend.modules.dashboard.api.dependencies import get_dashboard_service
from contractai_backend.modules.dashboard.api.routers import router
from contractai_backend.modules.dashboard.api.schemas import AreaChartProps, AreaChartResponse, AreaChartSeries, AreaChartYAxis
from contractai_backend.modules.dashboard.domain.value_objs import TopRankingSortBy
from contractai_backend.modules.documents.domain.value_objs import CurrencyType, DocumentType
from contractai_backend.shared.api.dependencies.security import get_current_user
from contractai_backend.shared.api.error_handlers import app_error_handler


def _make_app(mock_service) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/dashboard")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, organization_id=10)
    app.dependency_overrides[get_dashboard_service] = lambda: mock_service
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    return app


def _area_chart_response() -> AreaChartResponse:
    return AreaChartResponse(
        props=AreaChartProps(
            title="Ingresos Proyectados",
            subtitle="Historico vs. contratos asegurados a futuro",
            y_axis=AreaChartYAxis(labels=[0, 1000, 2000, 3000, 4000]),
            threshold_date=datetime(2026, 5, 1, tzinfo=UTC),
            series=[AreaChartSeries(currency="PEN", name="Ingresos", data=[])],
        )
    )


@pytest.mark.asyncio
async def test_area_chart_accepts_valid_currency_param():
    service = AsyncMock()
    service.get_area_chart.return_value = _area_chart_response()
    app = _make_app(service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard/area_chart/company?currency=PEN")

    assert response.status_code == 200
    service.get_area_chart.assert_awaited_once()
    assert service.get_area_chart.await_args.kwargs["document_type"] == DocumentType.COMPANY
    assert service.get_area_chart.await_args.kwargs["currency"] == CurrencyType.PEN


@pytest.mark.asyncio
async def test_top_companies_accepts_currency_and_sort_params():
    service = AsyncMock()
    service.get_top_companies.return_value = []
    app = _make_app(service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard/top_companies?currency=USD&sort_by=value")

    assert response.status_code == 200
    service.get_top_companies.assert_awaited_once()
    assert service.get_top_companies.await_args.kwargs["currency"] == CurrencyType.USD
    assert service.get_top_companies.await_args.kwargs["sort_by"] == TopRankingSortBy.VALUE


@pytest.mark.asyncio
async def test_top_services_accepts_currency_and_sort_params():
    service = AsyncMock()
    service.get_top_services.return_value = []
    app = _make_app(service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard/top_services?currency=EUR&sort_by=volume")

    assert response.status_code == 200
    service.get_top_services.assert_awaited_once()
    assert service.get_top_services.await_args.kwargs["currency"] == CurrencyType.EUR
    assert service.get_top_services.await_args.kwargs["sort_by"] == TopRankingSortBy.VOLUME


@pytest.mark.asyncio
async def test_invalid_currency_returns_422():
    service = AsyncMock()
    app = _make_app(service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard/area_chart/company?currency=ABC")

    assert response.status_code == 422
    service.get_area_chart.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_sort_by_returns_422():
    service = AsyncMock()
    app = _make_app(service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard/top_companies?sort_by=random")

    assert response.status_code == 422
    service.get_top_companies.assert_not_awaited()


@pytest.mark.asyncio
async def test_forbidden_error_returns_403():
    service = AsyncMock()
    service.get_area_chart.side_effect = ForbiddenError("No tienes permisos para acceder a este dashboard")
    app = _make_app(service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard/area_chart/labor")

    assert response.status_code == 403
    assert response.json()["message"] == "No tienes permisos para acceder a este dashboard"
