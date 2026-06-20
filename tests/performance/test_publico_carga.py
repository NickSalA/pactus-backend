r"""Test de carga — Endpoints Públicos y Estáticos.

Endpoints cubiertos:
  GET /              — Mensaje de bienvenida del backend   [peso: 10]
  GET /openapi.json  — Esquema de OpenAPI generado por FastAPI  [peso: 2]

Cómo ejecutar este archivo individualmente:
  uv run locust -f tests/performance/test_publico_carga.py --host http://localhost:8000 --users 100 --spawn-rate 10 --run-time 2m --headless
"""

import sys
from pathlib import Path

# Garantiza que performance_tests/ esté en sys.path sin importar
# desde dónde se invoque locust (raíz del proyecto o subdirectorio).
sys.path.insert(0, str(Path(__file__).parent))

from locust import HttpUser, between, task
# pyrefly: ignore [missing-import]
from locust_config import setup_logger

logger = setup_logger("publico")


class PublicoUser(HttpUser):
    """Simula usuarios accediendo a recursos públicos de la API."""

    wait_time = between(0.1, 1.0)  # Ritmo rápido para estresar el servidor web

    @task(10)
    def test_root(self) -> None:
        """GET / — Endpoint raíz."""
        with self.client.get(
            "/",
            name="[PUBLIC] GET /",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                logger.error("[GET /] Error: Status %s", resp.status_code)
                resp.failure(f"Status inesperado: {resp.status_code}")

    @task(2)
    def test_openapi_schema(self) -> None:
        """GET /openapi.json — Esquema de la API."""
        with self.client.get(
            "/openapi.json",
            name="[PUBLIC] GET /openapi.json",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                logger.error("[GET /openapi.json] Error: Status %s", resp.status_code)
                resp.failure(f"Status inesperado: {resp.status_code}")
