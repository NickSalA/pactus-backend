"""Tests for client validation middleware."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import pactus_backend.shared.api.middlewares as mw
from pactus_backend.shared.api.middlewares import ClientValidationMiddleware
from pactus_backend.shared.config import settings


@pytest.mark.asyncio
async def test_client_validation_middleware(monkeypatch):
    # 1. Crear app dummy de prueba
    app = FastAPI()
    app.add_middleware(ClientValidationMiddleware)

    @app.get("/test-route")
    async def dummy_route():
        return {"status": "ok"}

    # Mock settings
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://allowed-frontend.com"])
    monkeypatch.setattr(settings, "CLIENT_API_KEY", "super-secret-client-key")
    monkeypatch.setattr(settings, "DEBUG", False)

    # Forzar is_testing y is_debug a False en el modulo de middlewares para ejecutar la validacion real
    monkeypatch.setattr(mw, "is_testing", False)
    monkeypatch.setattr(mw, "is_debug", False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # A. OPTIONS request (CORS Preflight) should bypass validation
        res = await client.options("/test-route")
        assert res.status_code != 403

        # B. Request from allowed origin should pass
        res = await client.get("/test-route", headers={"Origin": "https://allowed-frontend.com"})
        assert res.status_code == 200

        # C. Request from disallowed origin should fail (403 Forbidden)
        res = await client.get("/test-route", headers={"Origin": "https://disallowed-frontend.com"})
        assert res.status_code == 403
        assert "Acceso denegado: origen no permitido." in res.json().get("detail")

        # D. Direct request without Origin but with correct X-App-Secret should pass
        res = await client.get("/test-route", headers={"X-App-Secret": "super-secret-client-key"})
        assert res.status_code == 200

        # E. Direct request without Origin and with incorrect X-App-Secret should fail
        res = await client.get("/test-route", headers={"X-App-Secret": "wrong-key"})
        assert res.status_code == 403
        assert "Acceso denegado: se requiere token de cliente válido." in res.json().get("detail")

        # F. Direct request without Origin and without X-App-Secret should fail
        res = await client.get("/test-route")
        assert res.status_code == 403
        assert "Acceso denegado: se requiere token de cliente válido." in res.json().get("detail")
