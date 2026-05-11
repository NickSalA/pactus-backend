"""Tests for application settings resolution."""

from unittest.mock import patch

import pytest

from contractai_backend.shared.config import Settings


def _secret_values() -> dict[str, str]:
    return {
        "SECRET-KEY": "vault-secret-key",
        "GEMINI-API-KEY": "vault-gemini-key",
        "OPENAI-API-KEY": "openai-key",
        "AZURE-OPENAI-API-KEY": "azure-openai-key",
        "QDRANT-API-KEY": "qdrant-key",
        "LLAMA-PARSE-API-KEY": "llama-key",
        "DATABASE-PASSWORD": "db-password",
        "DATABASE-USER": "db-user",
        "DATABASE-HOST": "db.example.com",
        "SUPABASE-SECRET-KEY": "supabase-secret",
        "GOOGLE-CLIENT-SECRET": "google-client-secret",
        "CRON-SECRET": "cron-secret",
    }


def _get_secret_from(values: dict[str, str]):
    def get_secret(secret_name: str) -> str:
        if secret_name not in values:
            raise ValueError(f"Missing secret: {secret_name}")
        return values[secret_name]

    return get_secret


def _clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "QDRANT_API_KEY",
        "QDRANT_URL",
        "LLAMA_PARSE_API_KEY",
        "DATABASE_PASSWORD",
        "DATABASE_USER",
        "DATABASE_HOST",
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI",
        "GMAIL_SENDER",
        "GMAIL_APP_PASSWORD",
        "CRON_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)


class TestSettings:
    def test_loads_missing_values_from_key_vault(self, monkeypatch):
        _clear_settings_env(monkeypatch)

        with patch("contractai_backend.shared.config.get_secret") as get_secret_mock:
            get_secret_mock.side_effect = _get_secret_from(_secret_values())

            settings = Settings(
                _env_file=None,
                QDRANT_URL="https://qdrant.example.com",
                SUPABASE_URL="https://supabase.example.com",
                GOOGLE_CLIENT_ID="google-client-id",
                GOOGLE_REDIRECT_URI="https://app.example.com/integrations/drive/callback",
            )

        assert settings.OPENAI_API_KEY == "openai-key"
        assert settings.GEMINI_API_KEY == "vault-gemini-key"
        assert settings.AZURE_OPENAI_API_KEY == "azure-openai-key"
        get_secret_mock.assert_any_call("OPENAI-API-KEY")

    def test_prefers_dotenv_values_over_key_vault(self, tmp_path, monkeypatch):
        _clear_settings_env(monkeypatch)

        env_values = {
            "GEMINI_API_KEY": "env-gemini-key",
            "OPENAI_API_KEY": "env-openai-key",
            "AZURE_OPENAI_API_KEY": "env-azure-openai-key",
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
            "CRON_SECRET": "cron-secret",
        }
        env_file = tmp_path / ".env"
        env_file.write_text(
            "\n".join(f'{key}="{value}"' for key, value in env_values.items()),
            encoding="utf-8",
        )

        with patch("contractai_backend.shared.config.get_secret") as get_secret_mock:
            settings = Settings(_env_file=env_file)

        assert settings.GEMINI_API_KEY == "env-gemini-key"
        assert settings.OPENAI_API_KEY == "env-openai-key"
        assert settings.AZURE_OPENAI_API_KEY == "env-azure-openai-key"
        get_secret_mock.assert_not_called()

    def test_raises_runtime_error_when_secret_provider_fails(self, monkeypatch):
        _clear_settings_env(monkeypatch)

        with patch("contractai_backend.shared.config.get_secret", side_effect=RuntimeError("Proveedor de secretos no configurado")):
            with pytest.raises(RuntimeError, match="Proveedor de secretos"):
                Settings(
                    _env_file=None,
                    QDRANT_URL="https://qdrant.example.com",
                    SUPABASE_URL="https://supabase.example.com",
                    GOOGLE_CLIENT_ID="google-client-id",
                    GOOGLE_REDIRECT_URI="https://app.example.com/integrations/drive/callback",
                )
