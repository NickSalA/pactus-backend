"""Archivo principal para la aplicación FastAPI de ContractAI-Backend."""

import asyncio
import sys

from fastapi import FastAPI
from loguru import logger
from uvicorn import run

from .shared.config import settings
from .shared.logger import setup

# Psycopg async is not compatible with the default Proactor loop on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

setup()

try:
    from contractai_backend.factory import create

    app: FastAPI = create()
except Exception as e:
    logger.exception("Error al crear la aplicación FastAPI: {}", e)
    raise


def main():
    """Función principal para ejecutar la aplicación FastAPI."""
    run(app="contractai_backend.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG, log_config=None)
