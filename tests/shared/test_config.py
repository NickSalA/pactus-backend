"""Tests for application settings resolution."""

from unittest.mock import patch

import pytest

from contractai_backend.shared.config import Settings


def _secret_values() -> dict[str, str]:
    return {
        "SECRET-KEY": "vault-secret-key",
        "GEMINI-API-KEY": "vault-gemini-key",
        "OPENAI-API-KEY": "openai-key",
        "QDRANT-API-KEY": "qdrant-key",
        "QDRANT-URL": "https://qdrant.example.com",
        "LLAMA-PARSE-API-KEY": "llama-key",
        "DATABASE-PASSWORD": "db-password",
        "DATABASE-USER": "db-user",
        "DATABASE-HOST": "db.example.com",
        "SUPABASE-URL": "https://supabase.example.com",
        "SUPABASE-SECRET-KEY": "supabase-secret",
        "GOOGLE-CLIENT-ID": "google-client-id",
        "GOOGLE-CLIENT-SECRET": "google-client-secret",
        "GOOGLE-REDIRECT-URI": "https://app.example.com/integrations/drive/callback",
    }


def _get_secret_from(values: dict[str, str]):
    def get_secret(vault_url: str, secret_name: str) -> str:
        assert vault_url == "https://test.vault.azure.net"
        if secret_name not in values:
            raise ValueError(f"Missing secret: {secret_name}")
        return values[secret_name]

    return get_secret


class TestSettings:
    def test_loads_missing_values_from_key_vault(self):
        with patch("contractai_backend.shared.config.SecretManager.get_secret") as get_secret_mock:
            get_secret_mock.side_effect = _get_secret_from(_secret_values())

            settings = Settings(_env_file=None, AZURE_KEY_VAULT_URL="https://test.vault.azure.net")

        assert settings.OPENAI_API_KEY == "openai-key"
        assert settings.SECRET_KEY == "vault-secret-key"
        assert settings.GEMINI_API_KEY == "vault-gemini-key"
        get_secret_mock.assert_any_call("https://test.vault.azure.net", "OPENAI-API-KEY")

    def test_prefers_dotenv_values_over_key_vault(self, tmp_path):
        env_values = {
            "AZURE_KEY_VAULT_URL": "https://test.vault.azure.net",
            "GEMINI_API_KEY": "env-gemini-key",
            "OPENAI_API_KEY": "env-openai-key",
            "QDRANT_API_KEY": "env-qdrant-key",
            "QDRANT_URL": "https://env.qdrant.example.com",
            "LLAMA_PARSE_API_KEY": "env-llama-key",
            "DATABASE_PASSWORD": "env-db-password",
            "DATABASE_USER": "env-db-user",
            "DATABASE_HOST": "env-db.example.com",
            "SUPABASE_URL": "https://env.supabase.example.com",
            "SUPABASE_SECRET_KEY": "env-supabase-secret",
            "GOOGLE_CLIENT_ID": "env-google-client-id",
            "GOOGLE_CLIENT_SECRET": "env-google-client-secret",
            "GOOGLE_REDIRECT_URI": "https://env.example.com/integrations/drive/callback",
            "GMAIL_SENDER": "alerts@example.com",
            "GMAIL_APP_PASSWORD": "app-password",
        }
        env_file = tmp_path / ".env"
        env_file.write_text(
            "\n".join(f'{key}="{value}"' for key, value in env_values.items()),
            encoding="utf-8",
        )

        with patch("contractai_backend.shared.config.SecretManager.get_secret") as get_secret_mock:
            settings = Settings(_env_file=env_file)

        assert settings.SECRET_KEY == "env-secret-key"
        assert settings.GEMINI_API_KEY == "env-gemini-key"
        assert settings.OPENAI_API_KEY == "env-openai-key"
        get_secret_mock.assert_not_called()

    def test_raises_runtime_error_when_secret_fallback_has_no_vault_url(self):
        with pytest.raises(RuntimeError, match="AZURE_KEY_VAULT_URL"):
            Settings(_env_file=None)
