"""Tests de setup y configuración básica de la aplicación."""

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app() -> FastAPI:
    """Crea la app FastAPI sin lifespan (sin efectos secundarios de infra)."""
    from pactus_backend.factory import create  # noqa: PLC0415
    return create()


@pytest.mark.asyncio
async def test_app_creates_successfully(app: FastAPI):
    """La factory debe crear la app sin lanzar excepciones."""
    assert app is not None
    assert isinstance(app, FastAPI)


@pytest.mark.asyncio
async def test_root_endpoint(app: FastAPI):
    """El endpoint raíz debe responder 200 con mensaje de bienvenida."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert "message" in body
    assert "version" in body


@pytest.mark.asyncio
async def test_documents_router_is_registered(app: FastAPI):
    """El router de documents debe estar registrado en la app."""
    routes = [route.path for route in app.routes]
    assert any("/documents" in path for path in routes)


@pytest.mark.asyncio
async def test_openapi_schema_is_available(app: FastAPI):
    """El schema OpenAPI debe estar disponible."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    assert "paths" in schema
    assert "openapi" in schema


@pytest.mark.asyncio
async def test_openapi_includes_refactored_response_contracts(app: FastAPI):
    """Critical refactored endpoints must expose their intended schemas."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/openapi.json")

    schema = response.json()
    template_generate = schema["paths"]["/templates/{template_id}/generate"]["post"]
    notification_cron = schema["paths"]["/notifications/cron/send-emails"]["post"]

    assert template_generate["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith("/DocumentResponse")
    assert set(notification_cron["responses"]) >= {"200", "401", "422", "503"}
