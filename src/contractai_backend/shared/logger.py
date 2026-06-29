"""Configuración de logging para la aplicación."""

import inspect
import logging
import sys
from typing import Any, cast

from loguru import logger

from .config import settings


class InterceptHandler(logging.Handler):
    """Intercepta logs de la librería estándar (logging) y los rutea a Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emite un registro de log."""
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup() -> None:
    """Configura el logging global de la aplicación."""
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    loggers_to_intercept = (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "sqlalchemy.engine",
        "httpx",
        "httpcore",
    )
    for logger_name in loggers_to_intercept:
        mod_logger = logging.getLogger(logger_name)
        mod_logger.handlers = [InterceptHandler()]
        mod_logger.propagate = False

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    handlers: list[dict[str, Any]] = [
        {
            "sink": sys.stderr,
            "level": settings.LOG_LEVEL,
            "format": "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            "diagnose": False,
            "backtrace": False,
        }
    ]

    if settings.DEBUG:
        handlers.append(
            {
                "sink": "logs/app.log",
                "rotation": "50 MB",
                "retention": "10 days",
                "compression": "zip",
                "serialize": True,
                "level": "INFO",
                "diagnose": True,
                "backtrace": True,
            }
        )

    logger.configure(handlers=cast(Any, handlers))
