"""Configuración compartida para todos los tests de rendimiento con Locust.

Este módulo provee:
  - Configuración de logging con timestamp y nombre descriptivo por prueba.
  - Variables de entorno centralizadas (URL base, credenciales de prueba).
  - Clase base AuthenticatedUser con flujo de login automático (Supabase Bearer token).
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Directorios
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Cargar automáticamente el archivo .env de la raíz del proyecto
load_dotenv(BASE_DIR.parent / ".env")

# ---------------------------------------------------------------------------
# Configuración de entorno  (sobre-escribir con variables de entorno reales)
# ---------------------------------------------------------------------------
BASE_URL: str = os.getenv("LOCUST_BASE_URL", "http://localhost:8000")

# En pruebas de rendimiento, apuntamos directamente a los endpoints reales.
# El middleware del backend se encarga de interceptarlos sin usar BD ni Supabase.
API_PREFIX: str = ""

# Credenciales de usuario de prueba (ADMIN) — deben existir en la DB
TEST_USER_EMAIL: str = os.getenv("LOCUST_USER_EMAIL") or os.getenv("TEST_USER_EMAIL") or "test_admin@example.com"
TEST_USER_PASSWORD: str = os.getenv("LOCUST_USER_PASSWORD") or os.getenv("TEST_USER_PASSWORD") or "SuperSecret123!"

# Credenciales de usuario WORKER (solo lectura)
TEST_WORKER_EMAIL: str = os.getenv("LOCUST_WORKER_EMAIL") or os.getenv("TEST_WORKER_EMAIL") or "test_worker@example.com"
TEST_WORKER_PASSWORD: str = os.getenv("LOCUST_WORKER_PASSWORD") or os.getenv("TEST_WORKER_PASSWORD") or "SuperSecret123!"

# IDs de recursos que ya existen en la BD de prueba
# (ajustar antes de correr contra un ambiente con datos reales)
SEED_DOCUMENT_ID: int = int(os.getenv("LOCUST_SEED_DOCUMENT_ID", "1"))
SEED_TEMPLATE_ID: int = int(os.getenv("LOCUST_SEED_TEMPLATE_ID", "1"))
SEED_FOLDER_ID: int = int(os.getenv("LOCUST_SEED_FOLDER_ID", "1"))
SEED_CONVERSATION_ID: int = int(os.getenv("LOCUST_SEED_CONVERSATION_ID", "1"))
SEED_USER_ID: int = int(os.getenv("LOCUST_SEED_USER_ID", "1"))

# Supabase endpoint para intercambiar email+password por un access_token
# El backend valida contra Supabase directamente, así que lo hacemos aquí también.
SUPABASE_URL: str = os.getenv("LOCUST_SUPABASE_URL") or os.getenv("SUPABASE_URL") or ""
SUPABASE_ANON_KEY: str = (
    os.getenv("LOCUST_SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_SECRET_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or ""
)


# ---------------------------------------------------------------------------
# Helpers de logging
# ---------------------------------------------------------------------------


def setup_logger(test_name: str) -> logging.Logger:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = LOGS_DIR / f"{test_name}_{timestamp}.log"

    logger = logging.getLogger(test_name)
    logger.setLevel(logging.DEBUG)

    # Evitar duplicación de handlers si el módulo se importa varias veces
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de archivo
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Logger inicializado. Guardando en: %s", log_filename)
    return logger


# ---------------------------------------------------------------------------
# Mixin de autenticación reutilizable
# ---------------------------------------------------------------------------


class SupabaseAuthMixin:
    """Mixin que agrega autenticación simplificada para pruebas de rendimiento.

    Inyecta un Bearer token simulado en los headers para que el middleware
    del backend intercepte las peticiones sin requerir conexión a Supabase.
    """

    email: str = TEST_USER_EMAIL
    password: str = TEST_USER_PASSWORD
    _logger: logging.Logger = logging.getLogger("locust.auth")

    def _get_supabase_token(self) -> str:
        """Retorna un token ficticio para bypass de Supabase."""
        return "performance_test_token"

    def on_start(self) -> None:
        """Inicializa el usuario virtual inyectando el token en los headers."""
        token = self._get_supabase_token()
        self.client.headers.update({"Authorization": f"Bearer {token}"})
        self._logger.info("Token de simulación inyectado para %s", self.email)
