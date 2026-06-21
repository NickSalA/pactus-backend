"""Tests for billing API routes."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.modules.billing.api.dependencies import get_paypal_subscription_service
from contractai_backend.modules.billing.api.routers import router
from contractai_backend.modules.billing.application.dto import ConfirmPayPalSubscriptionResponse


def _make_app(service) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/billing")
    app.dependency_overrides[get_paypal_subscription_service] = lambda: service
    return app


class TestPayPalSubscriptionRouter:
    @pytest.mark.asyncio
    async def test_confirms_subscription_without_authentication_dependency(self):
        service = AsyncMock()
        service.confirm_subscription.return_value = ConfirmPayPalSubscriptionResponse(
            organization_id=10,
            admin_email="admin@example.com",
            paypal_subscription_id="I-6Y983831YP445233M",
        )
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/billing/paypal/subscriptions/confirm",
                json={"subscription_id": "I-6Y983831YP445233M", "email": "ADMIN@EXAMPLE.COM"},
            )

        assert response.status_code == 201
        assert response.json() == {
            "organization_id": 10,
            "admin_email": "admin@example.com",
            "paypal_subscription_id": "I-6Y983831YP445233M",
        }
        payload = service.confirm_subscription.await_args.args[0]
        assert payload.subscription_id == "I-6Y983831YP445233M"
        assert payload.email == "admin@example.com"

    @pytest.mark.asyncio
    async def test_rejects_invalid_payload_before_service_call(self):
        service = AsyncMock()
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/billing/paypal/subscriptions/confirm",
                json={"subscription_id": " ", "email": "not-an-email"},
            )

        assert response.status_code == 422
        service.confirm_subscription.assert_not_awaited()
