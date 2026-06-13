r"""Test de carga para ruta del sistema real (/templates/) — Sin Base de Datos.

Cómo ejecutar este archivo individualmente:
  uv run locust -f tests/performance/test_templates_real_carga.py --host http://localhost:8001 --users 100 --spawn-rate 10 --run-time 1m --headless
"""

import sys
from pathlib import Path

# Garantiza que tests/performance/ esté en sys.path
sys.path.insert(0, str(Path(__file__).parent))

from locust import HttpUser, between, task

# pyrefly: ignore [missing-import]
from locust_config import setup_logger

logger = setup_logger("templates_real")


class TemplatesRealPerfUser(HttpUser):
    """Simula usuarios accediendo al listado de plantillas real del sistema."""

    wait_time = between(0.1, 1.0)

    @task
    def test_list_templates(self) -> None:
        """GET /templates/ — Llama a la ruta real del sistema."""
        headers = {
            "Authorization": "Bearer mock-performance-token",
            "Content-Type": "application/json",
        }
        with self.client.get(
            "/templates/",
            headers=headers,
            name="[REAL ROUTE] GET /templates/",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                logger.error("[GET /templates/] Error: Status %s, Response: %s", resp.status_code, resp.text)
                resp.failure(f"Status inesperado: {resp.status_code}")
