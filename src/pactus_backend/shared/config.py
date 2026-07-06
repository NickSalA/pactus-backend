"""Configuration settings for the application."""

import os

from dotenv import load_dotenv
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..core.domain.db_schemas import CHECKPOINT_SCHEMA
from .application.secret import SecretsRegistry, get_secret


class Settings(BaseSettings):
    """Configuration settings for the application."""

    PROJECT_NAME: str = "CONTRACT AI"
    LOG_LEVEL: str = "DEBUG"
    GLOBAL_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = [
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:9002",
        "https://contractia-kappa.vercel.app",
        "http://127.0.0.1:3000",
    ]
    DEBUG: bool = Field(default=False)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440)
    PENDING_DAYS: int = Field(default=30)

    GEMINI_MODEL_NAME: str = Field(default="gemini-2.5-flash")
    GEMINI_MINI_MODEL_NAME: str = Field(default="gemini-2.5-flash-lite")
    GEMINI_API_KEY: str = Field(default_factory=lambda: get_secret("GEMINI-API-KEY"))
    # MODEL_SECOND_API_KEY: str = Field(default="your-second-model-api-key")
    MODEL_TEMPERATURE: float = Field(default=0.7)
    MAX_DAILY_TOKENS_PER_USER: int = Field(default=1000000)

    GEMINI_INPUT_PRICE_PER_M: float = Field(default=0.00125)
    GEMINI_OUTPUT_PRICE_PER_M: float = Field(default=0.005)

    OPENAI_EMBEDDING_MODEL_NAME: str = Field(default="text-embedding-3-small")
    OPENAI_API_KEY: str = Field(default_factory=lambda: get_secret("OPENAI-API-KEY"))
    # BETTER_STACK_TOKEN: str = Field(default=...)
    # BETTER_STACK_HOST: str = Field(default=...)

    QDRANT_API_KEY: str = Field(default_factory=lambda: get_secret("QDRANT-API-KEY"))
    QDRANT_URL: str = Field(default=...)
    INDEX_NAME: str = Field(default="contracts_index")
    DRIVE_INDEX_NAME: str = Field(default="drive_contracts_index")

    LLAMA_PARSE_API_KEY: str = Field(default_factory=lambda: get_secret("LLAMA-PARSE-API-KEY"))


    ALLOWED_FILE_TYPES: list[str] = Field(default=["application/pdf", "text/plain"])
    MAX_FILE_SIZE: int = Field(default=5)
    MAX_NUM_PAGES: int = Field(default=10)
    MAX_ORGANIZATIONS_LIMIT: int = Field(default=50)

    DATABASE_NAME: str | None = Field(default="postgres")
    DATABASE_PASSWORD: str | None = Field(default_factory=lambda: get_secret("DATABASE-PASSWORD"))
    DATABASE_USER: str | None = Field(default_factory=lambda: get_secret("DATABASE-USER"))
    DATABASE_HOST: str | None = Field(default_factory=lambda: get_secret("DATABASE-HOST"))
    DATABASE_PORT: int | None = Field(default=5432)
    DATABASE_POOL_SIZE: int = Field(default=5)
    DATABASE_MAX_OVERFLOW: int = Field(default=5)
    DATABASE_POOL_TIMEOUT: int = Field(default=15)
    DATABASE_POOL_RECYCLE: int = Field(default=1800)
    DATABASE_SSL_VERIFY: bool = Field(default=False)
    CHECKPOINTER_POOL_MIN_SIZE: int = Field(default=1)
    CHECKPOINTER_POOL_MAX_SIZE: int = Field(default=2)
    CHECKPOINTER_SCHEMA: str = Field(default=CHECKPOINT_SCHEMA)

    SUPABASE_URL: str = Field(default=...)
    SUPABASE_SECRET_KEY: str = Field(default_factory=lambda: get_secret("SUPABASE-SECRET-KEY"))
    SUPABASE_STORAGE_BUCKET: str = Field(default_factory=lambda: get_secret("SUPABASE-STORAGE-BUCKET"))

    GOOGLE_CLIENT_ID: str = Field(default_factory=lambda: get_secret("GOOGLE-CLIENT-ID"))
    GOOGLE_CLIENT_SECRET: str = Field(default_factory=lambda: get_secret("GOOGLE-CLIENT-SECRET"))
    GOOGLE_REDIRECT_URI: str = Field(default=...)

    GMAIL_SENDER: str | None = Field(default=None)
    GMAIL_APP_PASSWORD: str | None = Field(default_factory=lambda: get_secret("GMAIL-APP-PASSWORD"))

    CRON_SECRET: str | None = Field(default_factory=lambda: get_secret("CRON-SECRET"))
    PAYPAL_CLIENT_ID: str | None = Field(default_factory=lambda: get_secret("PAYPAL-CLIENT-ID"))
    PAYPAL_CLIENT_SECRET: str | None = Field(default_factory=lambda: get_secret("PAYPAL-CLIENT-SECRET"))
    PAYPAL_BASE_URL: str = Field(default="https://api-m.sandbox.paypal.com")

    @property
    def DATABASE_URL(self) -> str:  # noqa: N802
        """Recupera la URL de la base de datos desde Key Vault o variable de entorno."""
        if not self.DATABASE_HOST:
            return "sqlite:///./test.db"
        return f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    @property
    def CONN_STRING(self) -> str:  # noqa: N802
        """Recupera la cadena de conexión para el checkpointer."""
        if not self.DATABASE_HOST:
            return "sqlite:///./test.db"
        return f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}?sslmode=require"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")

load_dotenv()

is_debug = os.environ.get("DEBUG", "False").lower() == "true"
is_testing = "PYTEST_CURRENT_TEST" in os.environ

if not is_debug and not is_testing:
    from .infrastructure.azure_provider import AzureKeyVaultProvider

    SecretsRegistry.set_provider(AzureKeyVaultProvider(vault_url="https://contractai.vault.azure.net/"))

try:
    settings = Settings()
except ValidationError as e:
    raise RuntimeError(f"Error de validación en la configuración: {e}") from e





