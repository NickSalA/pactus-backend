"""Tests unitarios para SupabaseAuthService."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from contractai_backend.core.exceptions.base import BadGatewayError, UnauthorizedError
from contractai_backend.modules.users.infrastructure.jwt_service import SupabaseAuthService


def _make_service(client=None) -> SupabaseAuthService:
    with patch("contractai_backend.modules.users.infrastructure.jwt_service.settings") as s:
        s.SUPABASE_URL = "https://fake.supabase.co"
        s.SUPABASE_SECRET_KEY = "fake-key"
        svc = SupabaseAuthService(client=client)
    return svc


def _mock_response(status_code: int, json_data: dict | None = None) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status_code
    r.json.return_value = json_data or {}
    return r


class TestGetAuthenticatedUser:
    @pytest.mark.asyncio
    async def test_returns_external_user_dto_on_success(self):
        uid = str(uuid4())
        payload = {
            "id": uid,
            "email": "user@example.com",
            "user_metadata": {"full_name": "Test User", "avatar_url": None},
        }
        mock_client = AsyncMock()
        mock_client.get.return_value = _mock_response(200, payload)

        svc = _make_service(client=mock_client)
        result = await svc.get_authenticated_user("valid-token")

        assert result.email == "user@example.com"
        assert result.full_name == "Test User"

    @pytest.mark.asyncio
    async def test_email_is_lowercased_and_stripped(self):
        uid = str(uuid4())
        payload = {"id": uid, "email": "  USER@EXAMPLE.COM  ", "user_metadata": {}}
        mock_client = AsyncMock()
        mock_client.get.return_value = _mock_response(200, payload)

        svc = _make_service(client=mock_client)
        result = await svc.get_authenticated_user("token")

        assert result.email == "user@example.com"

    @pytest.mark.asyncio
    async def test_202_raises_unauthorized(self):
        mock_client = AsyncMock()
        mock_client.get.return_value = _mock_response(202)

        svc = _make_service(client=mock_client)
        with pytest.raises(UnauthorizedError):
            await svc.get_authenticated_user("bad-token")

    @pytest.mark.asyncio
    async def test_403_raises_unauthorized(self):
        mock_client = AsyncMock()
        mock_client.get.return_value = _mock_response(403)

        svc = _make_service(client=mock_client)
        with pytest.raises(UnauthorizedError):
            await svc.get_authenticated_user("bad-token")

    @pytest.mark.asyncio
    async def test_500_raises_bad_gateway(self):
        mock_client = AsyncMock()
        mock_client.get.return_value = _mock_response(500)

        svc = _make_service(client=mock_client)
        with pytest.raises(BadGatewayError):
            await svc.get_authenticated_user("token")

    @pytest.mark.asyncio
    async def test_missing_email_raises_unauthorized(self):
        uid = str(uuid4())
        payload = {"id": uid, "email": None, "user_metadata": {}}
        mock_client = AsyncMock()
        mock_client.get.return_value = _mock_response(200, payload)

        svc = _make_service(client=mock_client)
        with pytest.raises(UnauthorizedError):
            await svc.get_authenticated_user("token")

    @pytest.mark.asyncio
    async def test_request_error_raises_bad_gateway(self):
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("conn error")

        svc = _make_service(client=mock_client)
        with pytest.raises(BadGatewayError):
            await svc.get_authenticated_user("token")
