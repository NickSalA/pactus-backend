"""Tests for integration routers with background imports."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.modules.integrations.api.routers import router
from contractai_backend.modules.integrations.api.schemas import ImportRequest
from contractai_backend.shared.api.dependencies.security import get_current_user
from contractai_backend.shared.config import settings


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/integrations")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=5, organization_id=9)
    return app


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
        expected_files_payload = [file_item.model_dump(mode="python") for file_item in import_request.files]

        with patch(
            "contractai_backend.modules.integrations.api.routers.process_drive_import_in_background",
            new_callable=AsyncMock,
        ) as mock_background_import:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/integrations/drive/import", json=payload)

        assert response.status_code == 200
        assert response.json() == {
            "message": "La importación ha comenzado en segundo plano.",
            "queued_files": 1,
            "index_name": settings.DRIVE_INDEX_NAME,
        }
        mock_background_import.assert_awaited_once_with(import_request.token, expected_files_payload, 9, 5)
