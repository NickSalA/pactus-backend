"""Tests unitarios para SupabaseStorageRepository mockeando httpx."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pactus_backend.modules.documents.domain.exceptions import DocumentStorageError, DocumentStorageUnavailableError
from pactus_backend.modules.documents.domain.value_objs import DocumentType
from pactus_backend.modules.documents.infrastructure.supabase_storage import SupabaseStorageRepository


def _make_repo() -> SupabaseStorageRepository:
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    with patch("pactus_backend.modules.documents.infrastructure.supabase_storage.settings") as mock_settings:
        mock_settings.SUPABASE_URL = "https://fake.supabase.co"
        mock_settings.SUPABASE_STORAGE_BUCKET = "documents"
        mock_settings.SUPABASE_SECRET_KEY = "fake-key"
        repo = SupabaseStorageRepository(client=mock_client)
    return repo


def _mock_response(status_code: int, json_data: dict | None = None, text: str = "") -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.text = text
    return response


# ---------------------------------------------------------------------------
# _sanitize_filename
# ---------------------------------------------------------------------------

class TestSanitizeFilename:
    def test_normal_filename_unchanged(self):
        repo = _make_repo()
        assert repo._sanitize_filename("contrato.pdf") == "contrato.pdf"

    def test_spaces_replaced_with_underscore(self):
        repo = _make_repo()
        assert repo._sanitize_filename("mi contrato.pdf") == "mi_contrato.pdf"

    def test_special_chars_replaced(self):
        repo = _make_repo()
        result = repo._sanitize_filename("contrato@2024!.pdf")
        assert "@" not in result
        assert "!" not in result

    def test_empty_result_defaults_to_document_pdf(self):
        repo = _make_repo()
        assert repo._sanitize_filename("...") == "document.pdf"

    def test_no_extension_adds_pdf(self):
        repo = _make_repo()
        assert repo._sanitize_filename("contrato") == "contrato.pdf"

    def test_path_strips_to_basename(self):
        repo = _make_repo()
        result = repo._sanitize_filename("some/path/file.pdf")
        assert "/" not in result
        assert result == "file.pdf"


# ---------------------------------------------------------------------------
# _build_path
# ---------------------------------------------------------------------------

class TestBuildPath:
    def test_builds_path_with_filename(self):
        repo = _make_repo()
        path = repo._build_path(document_id=1, organization_id=10, document_type=DocumentType.COMPANY, filename="contrato.pdf")
        assert path == "orgs/10/company/docs/1/contrato.pdf"

    def test_builds_path_without_filename(self):
        repo = _make_repo()
        path = repo._build_path(document_id=5, organization_id=20, document_type=None)
        assert path == "orgs/20/untyped/docs/5/document.pdf"


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------

class TestUploadFile:
    @pytest.mark.asyncio
    async def test_upload_success_returns_path(self):
        repo = _make_repo()
        repo.client.post = AsyncMock(return_value=_mock_response(201))

        path = await repo.upload_file(1, 10, DocumentType.LABOR, b"content", "file.pdf", "application/pdf")
        assert path == "orgs/10/labor/docs/1/file.pdf"

    @pytest.mark.asyncio
    async def test_upload_http_error_raises_storage_error(self):
        repo = _make_repo()
        repo.client.post = AsyncMock(return_value=_mock_response(500))

        with pytest.raises(DocumentStorageError):
            await repo.upload_file(1, 10, DocumentType.LABOR, b"content", "file.pdf", "application/pdf")

    @pytest.mark.asyncio
    async def test_upload_timeout_raises_unavailable(self):
        repo = _make_repo()
        repo.client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(DocumentStorageUnavailableError):
            await repo.upload_file(1, 10, DocumentType.LABOR, b"content", "file.pdf", "application/pdf")

    @pytest.mark.asyncio
    async def test_upload_request_error_raises_unavailable(self):
        repo = _make_repo()
        repo.client.post = AsyncMock(side_effect=httpx.RequestError("conn error"))

        with pytest.raises(DocumentStorageUnavailableError):
            await repo.upload_file(1, 10, DocumentType.LABOR, b"content", "file.pdf", "application/pdf")


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------

class TestDeleteFile:
    @pytest.mark.asyncio
    async def test_delete_success(self):
        repo = _make_repo()
        repo.client.delete = AsyncMock(return_value=_mock_response(200))
        await repo.delete_file("documents/1/file.pdf")

    @pytest.mark.asyncio
    async def test_delete_not_found_is_silent(self):
        repo = _make_repo()
        repo.client.delete = AsyncMock(return_value=_mock_response(404))
        await repo.delete_file("documents/1/file.pdf")

    @pytest.mark.asyncio
    async def test_delete_bad_request_not_found_body_is_silent(self):
        repo = _make_repo()
        repo.client.delete = AsyncMock(return_value=_mock_response(400, text="object not found"))
        await repo.delete_file("documents/1/file.pdf")

    @pytest.mark.asyncio
    async def test_delete_server_error_raises_storage_error(self):
        repo = _make_repo()
        repo.client.delete = AsyncMock(return_value=_mock_response(500))

        with pytest.raises(DocumentStorageError):
            await repo.delete_file("documents/1/file.pdf")

    @pytest.mark.asyncio
    async def test_delete_timeout_raises_unavailable(self):
        repo = _make_repo()
        repo.client.delete = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(DocumentStorageUnavailableError):
            await repo.delete_file("documents/1/file.pdf")


# ---------------------------------------------------------------------------
# create_signed_url
# ---------------------------------------------------------------------------

class TestCreateSignedUrl:
    @pytest.mark.asyncio
    async def test_returns_full_signed_url(self):
        repo = _make_repo()
        repo.client.post = AsyncMock(return_value=_mock_response(200, json_data={"signedURL": "/object/sign/documents/1/file.pdf?token=abc"}))

        url = await repo.create_signed_url("documents/1/file.pdf")
        assert url.startswith("https://fake.supabase.co/storage/v1")
        assert "token=abc" in url

    @pytest.mark.asyncio
    async def test_missing_signed_url_in_response_raises(self):
        repo = _make_repo()
        repo.client.post = AsyncMock(return_value=_mock_response(200, json_data={}))

        with pytest.raises(DocumentStorageError):
            await repo.create_signed_url("documents/1/file.pdf")

    @pytest.mark.asyncio
    async def test_http_error_raises_storage_error(self):
        repo = _make_repo()
        repo.client.post = AsyncMock(return_value=_mock_response(403))

        with pytest.raises(DocumentStorageError):
            await repo.create_signed_url("documents/1/file.pdf")

    @pytest.mark.asyncio
    async def test_timeout_raises_unavailable(self):
        repo = _make_repo()
        repo.client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with pytest.raises(DocumentStorageUnavailableError):
            await repo.create_signed_url("documents/1/file.pdf")
