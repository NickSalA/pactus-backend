"""Configuración global de pytest para todos los módulos."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app() -> FastAPI:
    """Crea la app FastAPI sin lifespan (sin efectos secundarios de infra)."""
    from pactus_backend.factory import create
    return create()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    """Cliente HTTP async para tests de API."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
