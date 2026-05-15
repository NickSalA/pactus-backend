"""Tests for application settings resolution."""

import pytest
from pydantic import ValidationError

from contractai_backend.shared.config import Settings


def _settings_values() -> dict[str, str]:
    return {
        "GEMINI_API_KEY": "env-gemini-key",
        "OPENAI_API_KEY": "env-openai-key",
        "AZURE_OPENAI_API_KEY": "env-azure-openai-key",
        "QDRANT_API_KEY": "env-qdrant-key",
        "QDRANT_URL": "https://env.qdrant.example.com",
        "LLAMA_PARSE_API_KEY": "env-llama-key",
        "SUPABASE_URL": "https://env.supabase.example.com",
        "SUPABASE_SECRET_KEY": "env-supabase-secret",
        "GOOGLE_CLIENT_ID": "env-google-client-id",
        "GOOGLE_CLIENT_SECRET": "env-google-client-secret",
        "GOOGLE_REDIRECT_URI": "https://env.example.com/integrations/drive/callback",
    }


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
    def test_loads_values_from_dotenv(self, tmp_path, monkeypatch):
        _clear_settings_env(monkeypatch)

        env_values = _settings_values() | {
            "DATABASE_PASSWORD": "env-db-password",
            "DATABASE_USER": "env-db-user",
            "DATABASE_HOST": "env-db.example.com",
            "GMAIL_SENDER": "alerts@example.com",
            "GMAIL_APP_PASSWORD": "app-password",
        }
        env_file = tmp_path / ".env"
        env_file.write_text(
            "\n".join(f'{key}="{value}"' for key, value in env_values.items()),
            encoding="utf-8",
        )

        settings = Settings(_env_file=env_file)

        assert settings.GEMINI_API_KEY == "env-gemini-key"
        assert settings.OPENAI_API_KEY == "env-openai-key"
        assert settings.AZURE_OPENAI_API_KEY == "env-azure-openai-key"
        assert settings.CRON_SECRET is None

    def test_database_settings_are_optional_without_key_vault(self, monkeypatch):
        _clear_settings_env(monkeypatch)

        settings = Settings(_env_file=None, **_settings_values())

        assert settings.DATABASE_HOST is None
        assert settings.DATABASE_URL == "sqlite:///./test.db"

    def test_raises_validation_error_when_required_env_values_are_missing(self, monkeypatch):
        _clear_settings_env(monkeypatch)

        with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
            Settings(_env_file=None)
