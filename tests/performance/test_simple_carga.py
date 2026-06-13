r"""Test de carga simple — Endpoint de prueba sin Base de Datos.

Cómo ejecutar este archivo individualmente:
  uv run locust -f tests/performance_tests/test_simple_carga.py --host http://localhost:8000 --users 100 --spawn-rate 10 --run-time 1m --headless
"""

import sys
from pathlib import Path

# Garantiza que performance_tests/ esté en sys.path sin importar
# desde dónde se invoque locust.
sys.path.insert(0, str(Path(__file__).parent))

from locust import HttpUser, between, task
# pyrefly: ignore [missing-import]
from locust_config import setup_logger

logger = setup_logger("simple")


class SimplePerfUser(HttpUser):
    """Simula usuarios accediendo al endpoint de prueba de rendimiento sin DB ni Supabase."""

    wait_time = between(0.1, 1.0)

    @task
    def test_simple_endpoint(self) -> None:
        """GET /perf-test-data — Endpoint simple sin base de datos."""
        with self.client.get(
            "/perf-test-data",
            name="[SIMPLE] GET /perf-test-data",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                logger.error("[GET /perf-test-data] Error: Status %s", resp.status_code)
                resp.failure(f"Status inesperado: {resp.status_code}")
