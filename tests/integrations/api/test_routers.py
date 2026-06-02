"""Tests for integration routers with background imports."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.modules.integrations.api.dependencies import job_registry
from contractai_backend.modules.integrations.api.routers import router
from contractai_backend.modules.integrations.api.schemas import ImportRequest
from contractai_backend.shared.api.dependencies.security import get_current_user
from contractai_backend.shared.config import settings


def _make_app(user_id: int = 5, organization_id: int = 9) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/integrations")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id, organization_id=organization_id)
    return app


@pytest.fixture(autouse=True)
def clear_job_registry():
    job_registry._jobs.clear()
    job_registry._user_jobs.clear()
    yield
    job_registry._jobs.clear()
    job_registry._user_jobs.clear()


class TestImportDriveFiles:
    @pytest.mark.asyncio
    async def test_import_route_queues_background_job_with_raw_payload(self):
        app = _make_app()
        payload = {
            "token": {"token": "drive-token"},
            "files": [
                {
                    "file_id": "drive-file-1",
                    "document": {
                        "name": "Contrato desde Drive",
                        "client": "Cliente Test",
                        "type": "COMPANY",
                        "start_date": "2024-01-01",
                        "end_date": "2024-12-31",
                        "form_data": {"owner": "IT", "value": 1000, "currency": "USD"},
                        "service_items": [],
                    },
                }
            ],
        }
        import_request = ImportRequest.model_validate(payload)
        expected_files_payload = [file_item.model_dump(mode="python", exclude_unset=True, exclude_none=True) for file_item in import_request.files]

        with patch(
            "contractai_backend.modules.integrations.api.routers.process_drive_import_in_background",
            new_callable=AsyncMock,
        ) as mock_background_import:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/integrations/drive/import", json=payload)

        assert response.status_code == 200
        response_payload = response.json()
        assert response_payload == {
            "message": "La importación ha comenzado en segundo plano.",
            "queued_files": 1,
            "index_name": settings.DRIVE_INDEX_NAME,
            "job_id": response_payload["job_id"],
        }
        assert response_payload["job_id"]
        assert response_payload["job_id"] in job_registry._jobs
        mock_background_import.assert_awaited_once_with(response_payload["job_id"], import_request.token, expected_files_payload, 9, 5)

    @pytest.mark.asyncio
    async def test_import_route_accepts_files_without_document_payload(self):
        app = _make_app()
        payload = {
            "token": {"token": "drive-token"},
            "files": [
                {
                    "file_id": "drive-file-1",
                }
            ],
        }
        import_request = ImportRequest.model_validate(payload)
        expected_files_payload = [file_item.model_dump(mode="python", exclude_unset=True, exclude_none=True) for file_item in import_request.files]

        with patch(
            "contractai_backend.modules.integrations.api.routers.process_drive_import_in_background",
            new_callable=AsyncMock,
        ) as mock_background_import:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/integrations/drive/import", json=payload)

        assert response.status_code == 200
        response_payload = response.json()
        assert response_payload["job_id"]
        assert response_payload["job_id"] in job_registry._jobs
        mock_background_import.assert_awaited_once_with(response_payload["job_id"], import_request.token, expected_files_payload, 9, 5)

    @pytest.mark.asyncio
    async def test_import_route_preserves_empty_document_overrides_as_empty_object(self):
        app = _make_app()
        payload = {
            "token": {"token": "drive-token"},
            "files": [
                {
                    "file_id": "drive-file-1",
                    "document": {},
                }
            ],
        }

        with patch(
            "contractai_backend.modules.integrations.api.routers.process_drive_import_in_background",
            new_callable=AsyncMock,
        ) as mock_background_import:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/integrations/drive/import", json=payload)

        assert response.status_code == 200
        response_payload = response.json()
        assert response_payload["job_id"]
        assert response_payload["job_id"] in job_registry._jobs
        mock_background_import.assert_awaited_once_with(
            response_payload["job_id"],
            {"token": "drive-token"},
            [{"file_id": "drive-file-1", "document": {}}],
            9,
            5,
        )

    @pytest.mark.asyncio
    async def test_import_route_drops_null_document_fields_before_background_job(self):
        app = _make_app()
        payload = {
            "token": {"token": "drive-token"},
            "files": [
                {
                    "file_id": "drive-file-1",
                    "document": {
                        "name": None,
                        "client": None,
                        "type": None,
                        "start_date": None,
                        "end_date": None,
                    },
                }
            ],
        }

        with patch(
            "contractai_backend.modules.integrations.api.routers.process_drive_import_in_background",
            new_callable=AsyncMock,
        ) as mock_background_import:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/integrations/drive/import", json=payload)

        assert response.status_code == 200
        response_payload = response.json()
        assert response_payload["job_id"]
        assert response_payload["job_id"] in job_registry._jobs
        mock_background_import.assert_awaited_once_with(
            response_payload["job_id"],
            {"token": "drive-token"},
            [{"file_id": "drive-file-1", "document": {}}],
            9,
            5,
        )

    @pytest.mark.asyncio
    async def test_import_route_blocks_duplicate_active_job(self):
        app = _make_app()
        payload = {
            "token": {"token": "drive-token"},
            "files": [{"file_id": "drive-file-1"}],
        }

        with patch(
            "contractai_backend.modules.integrations.api.routers.process_drive_import_in_background",
            new_callable=AsyncMock,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                first_response = await client.post("/integrations/drive/import", json=payload)

        assert first_response.status_code == 200

        with patch(
            "contractai_backend.modules.integrations.api.routers.process_drive_import_in_background",
            new_callable=AsyncMock,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                second_response = await client.post("/integrations/drive/import", json=payload)

        assert second_response.status_code == 409
        assert second_response.json()["detail"] == "Ya existe una importación en progreso. Espere a que termine."

    @pytest.mark.asyncio
    async def test_import_events_returns_404_for_unknown_job(self):
        app = _make_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/integrations/drive/import/fake-job-id/events")

        assert response.status_code == 404
        assert response.json()["detail"] == "Trabajo no encontrado."

    @pytest.mark.asyncio
    async def test_import_events_returns_403_for_wrong_user(self):
        app_user5 = _make_app(user_id=5)
        app_user7 = _make_app(user_id=7)
        payload = {
            "token": {"token": "drive-token"},
            "files": [{"file_id": "drive-file-1"}],
        }

        with patch(
            "contractai_backend.modules.integrations.api.routers.process_drive_import_in_background",
            new_callable=AsyncMock,
        ):
            async with AsyncClient(transport=ASGITransport(app=app_user5), base_url="http://test") as client:
                response = await client.post("/integrations/drive/import", json=payload)

        assert response.status_code == 200
        job_id = response.json()["job_id"]

        async with AsyncClient(transport=ASGITransport(app=app_user7), base_url="http://test") as client:
            response = await client.get(f"/integrations/drive/import/{job_id}/events")

        assert response.status_code == 403
        assert response.json()["detail"] == "No tiene acceso a este trabajo."
