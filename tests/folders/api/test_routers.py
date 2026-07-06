"""Tests for folder routers with mocked dependencies."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pactus_backend.modules.folders.api.dependencies import get_folder_service
from pactus_backend.modules.folders.api.routers import router
from pactus_backend.modules.folders.application.dto import FolderResponse
from pactus_backend.modules.users.domain.entities import UserTable
from pactus_backend.modules.users.domain.value_objs import UserRole
from pactus_backend.shared.api.dependencies.security import get_current_user


def _make_app(mock_service) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/folders")
    app.dependency_overrides[get_current_user] = lambda: UserTable(
        id=1,
        organization_id=1,
        email="manager@example.com",
        full_name="Manager User",
        role=UserRole.MANAGER,
        is_active=True,
    )
    app.dependency_overrides[get_folder_service] = lambda: mock_service
    return app


def _folder_response(name: str = "Contratos") -> FolderResponse:
    created_at = datetime(2026, 5, 17, tzinfo=UTC)
    return FolderResponse(
        id=5,
        organization_id=1,
        name=name,
        owner_role=UserRole.MANAGER,
        created_by=1,
        created_by_name="Manager User",
        created_by_email="manager@example.com",
        documents_count=2,
        created_at=created_at,
        updated_at=created_at,
    )


class TestFolderRouter:
    @pytest.mark.asyncio
    async def test_list_folders_accepts_application_dtos(self):
        service = AsyncMock()
        service.list_folders.return_value = [_folder_response()]
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/folders/")

        assert response.status_code == 200
        assert response.json()[0]["id"] == 5
        assert response.json()[0]["documents_count"] == 2

    @pytest.mark.asyncio
    async def test_create_folder_accepts_application_dto(self):
        service = AsyncMock()
        service.create_folder.return_value = _folder_response(name="Nuevos")
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/folders/", json={"name": "Nuevos"})

        assert response.status_code == 201
        assert response.json()["name"] == "Nuevos"

    @pytest.mark.asyncio
    async def test_update_folder_accepts_application_dto(self):
        service = AsyncMock()
        service.update_folder.return_value = _folder_response(name="Actualizados")
        app = _make_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/folders/5", json={"name": "Actualizados"})

        assert response.status_code == 200
        assert response.json()["name"] == "Actualizados"
