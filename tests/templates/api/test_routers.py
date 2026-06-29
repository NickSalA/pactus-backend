"""Tests for template routers with mocked dependencies."""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pactus_backend.modules.documents.domain import DocumentType
from pactus_backend.modules.templates.api.dependencies import get_template_authoring_service
from pactus_backend.modules.templates.api.routers import router
from pactus_backend.modules.templates.application.dto import TemplateFormatResponse
from pactus_backend.modules.users.domain.entities import UserTable
from pactus_backend.modules.users.domain.value_objs import UserRole
from pactus_backend.shared.api.dependencies.security import get_current_user


def _make_app(mock_authoring_service) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/templates")
    app.dependency_overrides[get_current_user] = lambda: UserTable(
        id=1,
        organization_id=1,
        email="manager@example.com",
        full_name="Manager User",
        role=UserRole.MANAGER,
        is_active=True,
    )
    app.dependency_overrides[get_template_authoring_service] = lambda: mock_authoring_service
    return app


class TestTemplateRouter:
    @pytest.mark.asyncio
    async def test_list_formats_accepts_application_dtos(self):
        service = AsyncMock()
        service.list_available_formats.return_value = [
            TemplateFormatResponse(
                id=1,
                document_type=DocumentType.COMPANY,
                format_code="management",
                label="Contrato base empresa",
                default_name="Contrato de servicios",
                default_description="Plantilla base para contratos de servicios.",
            )
        ]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/templates/formats")

        assert response.status_code == 200
        assert response.json()[0]["format_code"] == "management"
