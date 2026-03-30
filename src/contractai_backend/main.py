"""Archivo principal para la aplicación FastAPI de ContractAI-Backend."""
from fastapi import FastAPI
from loguru import logger
from uvicorn import run

from .shared.config import settings
from .shared.logger import setup

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
