r"""Test de carga de Renderizado de Plantillas — Prueba sin Base de Datos.

Cómo ejecutar este archivo individualmente:
  uv run locust -f tests/performance_tests/test_render_carga.py --host http://localhost:8000 --users 100 --spawn-rate 10 --run-time 1m --headless
"""

import random
import sys
from pathlib import Path

# Garantiza que performance_tests/ esté en sys.path sin importar
# desde dónde se invoque locust.
sys.path.insert(0, str(Path(__file__).parent))

from locust import HttpUser, between, task
# pyrefly: ignore [missing-import]
from locust_config import setup_logger

logger = setup_logger("render")

COMPANIES = ["Acme Corp", "Tech Solutions", "Global Logistics", "Innova Soft"]
CLIENTS = ["Andrés Pérez", "María Silva", "Carlos Ortega", "Laura Mendoza"]
CURRENCIES = ["USD", "PEN", "EUR"]


class RenderPerfUser(HttpUser):
    """Simula usuarios enviando peticiones POST para renderizar borradores de contratos."""

    wait_time = between(0.1, 1.0)

    @task
    def test_render_template(self) -> None:
        """POST /perf-render-template — Renderizado simulado sin base de datos."""
        payload = {
            "company": random.choice(COMPANIES),
            "client": random.choice(CLIENTS),
            "value": str(random.randint(1000, 99999)),
            "currency": random.choice(CURRENCIES),
        }
        with self.client.post(
            "/perf-render-template",
            json=payload,
            name="[RENDER] POST /perf-render-template",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                logger.error("[POST /perf-render-template] Error: Status %s", resp.status_code)
                resp.failure(f"Status inesperado: {resp.status_code}")
