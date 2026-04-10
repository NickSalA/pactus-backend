"""Unit tests for the Azure Key Vault secrets provider."""

from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import AzureError, ClientAuthenticationError, ResourceNotFoundError

from contractai_backend.shared.infrastructure.secrets_provider import AzureKeyVaultSecretsProvider


def _make_provider(client: MagicMock | None = None) -> tuple[AzureKeyVaultSecretsProvider, MagicMock]:
    mock_client = client or MagicMock()

    with (
        patch("contractai_backend.shared.infrastructure.secrets_provider.DefaultAzureCredential", return_value=MagicMock()),
        patch("contractai_backend.shared.infrastructure.secrets_provider.SecretClient", return_value=mock_client),
    ):
        provider = AzureKeyVaultSecretsProvider("https://test.vault.azure.net")

    return provider, mock_client


class TestGetSecret:
    def test_returns_secret_value(self):
        provider, client = _make_provider()
        client.get_secret.return_value = MagicMock(value="secret-value")

        result = provider.get_secret("DATABASE_PASSWORD")

        assert result == "secret-value"
        client.get_secret.assert_called_once_with("DATABASE_PASSWORD")

    def test_raises_value_error_when_secret_is_missing(self):
        provider, client = _make_provider()
        client.get_secret.side_effect = ResourceNotFoundError("missing secret")

        with pytest.raises(ValueError, match="no existe"):
            provider.get_secret("DATABASE_PASSWORD")

    def test_raises_runtime_error_on_authentication_failure(self):
        provider, client = _make_provider()
        client.get_secret.side_effect = ClientAuthenticationError("invalid credentials")

        with pytest.raises(RuntimeError, match="autenticar"):
            provider.get_secret("DATABASE_PASSWORD")

    def test_raises_runtime_error_on_unexpected_azure_error(self):
        provider, client = _make_provider()
        client.get_secret.side_effect = AzureError("service unavailable")

        with pytest.raises(RuntimeError, match="No se pudo recuperar"):
            provider.get_secret("DATABASE_PASSWORD")

    def test_raises_value_error_when_secret_has_no_value(self):
        provider, client = _make_provider()
        client.get_secret.return_value = MagicMock(value=None)

        with pytest.raises(ValueError, match="no tiene valor"):
            provider.get_secret("DATABASE_PASSWORD")
