"""Tests for integration routers with background imports."""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contractai_backend.core.exceptions.base import AppError
from contractai_backend.modules.integrations.api.dependencies import get_integration_service
from contractai_backend.modules.integrations.application.jobs import job_registry
from contractai_backend.modules.integrations.api.routers import router
from contractai_backend.modules.integrations.api.schemas import ImportRequest
from contractai_backend.modules.integrations.application.services.integration_service import IntegrationService
from contractai_backend.modules.integrations.domain.exceptions import InvalidCloudTokenError
from contractai_backend.modules.integrations.infrastructure.google_drive_provider import GOOGLE_DRIVE_FILE_SCOPE, GoogleDriveProvider
from contractai_backend.shared.api.dependencies.security import get_current_user
from contractai_backend.shared.api.error_handlers import app_error_handler
from contractai_backend.shared.config import settings


def _make_app(user_id: int = 5, organization_id: int = 9) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/integrations")
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=user_id,
        organization_id=organization_id,
        email=f"user-{user_id}@example.com",
        full_name=f"User {user_id}",
        role=None,
    )
    return app


def _expected_imported_by(user_id: int = 5, organization_id: int = 9) -> dict:
    return {
        "id": user_id,
        "organization_id": organization_id,
        "email": f"user-{user_id}@example.com",
        "full_name": f"User {user_id}",
        "role": None,
        "is_active": True,
    }


def _make_oauth_app(service) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/integrations")
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.dependency_overrides[get_integration_service] = lambda: service
    return app


def _parse_auth_url(url: str):
    parsed = urlparse(url)
    return parsed, parse_qs(parsed.query)


@pytest.fixture(autouse=True)
def clear_job_registry():
    job_registry._jobs.clear()
    job_registry._user_jobs.clear()
    yield
    job_registry._jobs.clear()
    job_registry._user_jobs.clear()


class TestGoogleDriveOAuthFlow:
    @pytest.mark.asyncio
    async def test_auth_url_returns_google_oauth_url_for_panel(self):
        provider = GoogleDriveProvider(
            client_id="verified-client-id.apps.googleusercontent.com",
            client_secret="test-client-secret",
            redirect_uri="https://verified.example.com/integrations/drive/callback",
        )
        service = IntegrationService(provider=provider, ingestion_target=AsyncMock(), index_name="drive-test-index")
        app = _make_oauth_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/integrations/drive/auth-url")

        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"url"}
        parsed, query = _parse_auth_url(payload["url"])
        assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://accounts.google.com/o/oauth2/auth"
        assert query["client_id"] == ["verified-client-id.apps.googleusercontent.com"]
        assert query["response_type"] == ["code"]

    @pytest.mark.asyncio
    async def test_auth_url_uses_verified_redirect_uri_and_drive_file_scope(self):
        redirect_uri = "https://verified.example.com/integrations/drive/callback"
        provider = GoogleDriveProvider(
            client_id="verified-client-id.apps.googleusercontent.com",
            client_secret="test-client-secret",
            redirect_uri=redirect_uri,
        )
        service = IntegrationService(provider=provider, ingestion_target=AsyncMock(), index_name="drive-test-index")
        app = _make_oauth_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/integrations/drive/auth-url")

        assert response.status_code == 200
        _parsed, query = _parse_auth_url(response.json()["url"])
        assert query["redirect_uri"] == [redirect_uri]
        assert query["scope"] == [GOOGLE_DRIVE_FILE_SCOPE]
        assert "https://www.googleapis.com/auth/drive" not in query["scope"]
        assert query["access_type"] == ["offline"]
        assert query["prompt"] == ["consent"]

    @pytest.mark.asyncio
    async def test_auth_url_does_not_expose_client_secret(self):
        provider = GoogleDriveProvider(
            client_id="verified-client-id.apps.googleusercontent.com",
            client_secret="super-secret-value",
            redirect_uri="https://verified.example.com/integrations/drive/callback",
        )
        service = IntegrationService(provider=provider, ingestion_target=AsyncMock(), index_name="drive-test-index")
        app = _make_oauth_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/integrations/drive/auth-url")

        assert response.status_code == 200
        auth_url = response.json()["url"]
        _parsed, query = _parse_auth_url(auth_url)
        assert "client_secret" not in query
        assert "super-secret-value" not in auth_url

    @pytest.mark.asyncio
    async def test_auth_url_contains_required_oauth_query_params(self):
        provider = GoogleDriveProvider(
            client_id="verified-client-id.apps.googleusercontent.com",
            client_secret="test-client-secret",
            redirect_uri="https://verified.example.com/integrations/drive/callback",
        )
        service = IntegrationService(provider=provider, ingestion_target=AsyncMock(), index_name="drive-test-index")
        app = _make_oauth_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/integrations/drive/auth-url")

        assert response.status_code == 200
        _parsed, query = _parse_auth_url(response.json()["url"])
        assert {
            "client_id",
            "redirect_uri",
            "response_type",
            "scope",
            "access_type",
            "prompt",
        }.issubset(query)
        assert query["response_type"] == ["code"]

    @pytest.mark.asyncio
    async def test_callback_exchanges_code_and_returns_token_payload(self):
        service = AsyncMock()
        service.authenticate.return_value = {
            "token": "access-token",
            "refresh_token": "refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "verified-client-id.apps.googleusercontent.com",
            "client_secret": "test-client-secret",
            "scopes": [GOOGLE_DRIVE_FILE_SCOPE],
        }
        app = _make_oauth_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/integrations/drive/callback?code=valid-code")

        assert response.status_code == 200
        assert response.json() == {
            "token": "access-token",
            "refresh_token": "refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "verified-client-id.apps.googleusercontent.com",
            "client_secret": "test-client-secret",
            "scopes": [GOOGLE_DRIVE_FILE_SCOPE],
        }
        service.authenticate.assert_awaited_once_with(code="valid-code")

    @pytest.mark.asyncio
    async def test_callback_accepts_token_payload_without_refresh_token(self):
        service = AsyncMock()
        service.authenticate.return_value = {
            "token": "access-token",
            "refresh_token": None,
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "verified-client-id.apps.googleusercontent.com",
            "client_secret": "test-client-secret",
            "scopes": [GOOGLE_DRIVE_FILE_SCOPE],
        }
        app = _make_oauth_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/integrations/drive/callback?code=already-consented-code")

        assert response.status_code == 200
        assert response.json() == {
            "token": "access-token",
            "refresh_token": None,
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "verified-client-id.apps.googleusercontent.com",
            "client_secret": "test-client-secret",
            "scopes": [GOOGLE_DRIVE_FILE_SCOPE],
        }
        service.authenticate.assert_awaited_once_with(code="already-consented-code")

    @pytest.mark.asyncio
    async def test_callback_requires_code_query_param(self):
        service = AsyncMock()
        app = _make_oauth_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/integrations/drive/callback")

        assert response.status_code == 422
        service.authenticate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_callback_empty_code_returns_controlled_error(self):
        service = AsyncMock()
        service.authenticate.side_effect = InvalidCloudTokenError("El código de autorización proporcionado es inválido o ha expirado.")
        app = _make_oauth_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/integrations/drive/callback?code=")

        assert response.status_code == 401
        assert response.json()["message"] == "El código de autorización proporcionado es inválido o ha expirado."
        service.authenticate.assert_awaited_once_with(code="")

    @pytest.mark.asyncio
    async def test_callback_invalid_code_returns_controlled_error(self):
        service = AsyncMock()
        service.authenticate.side_effect = InvalidCloudTokenError("El código de autorización proporcionado es inválido o ha expirado.")
        app = _make_oauth_app(service)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/integrations/drive/callback?code=expired-code")

        assert response.status_code == 401
        assert response.json()["message"] == "El código de autorización proporcionado es inválido o ha expirado."
        service.authenticate.assert_awaited_once_with(code="expired-code")


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
        mock_background_import.assert_awaited_once_with(
            response_payload["job_id"],
            import_request.token,
            expected_files_payload,
            9,
            5,
            _expected_imported_by(),
        )

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
        mock_background_import.assert_awaited_once_with(
            response_payload["job_id"],
            import_request.token,
            expected_files_payload,
            9,
            5,
            _expected_imported_by(),
        )

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
            _expected_imported_by(),
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
            _expected_imported_by(),
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
        assert second_response.json()["message"] == "Ya existe una importación en progreso. Espere a que termine."

    @pytest.mark.asyncio
    async def test_import_events_returns_404_for_unknown_job(self):
        app = _make_app()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/integrations/drive/import/fake-job-id/events")

        assert response.status_code == 404
        assert response.json()["message"] == "Trabajo no encontrado."

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
        assert response.json()["message"] == "No tiene acceso a este trabajo."
