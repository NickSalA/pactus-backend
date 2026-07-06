"""Middleware personalizado para logging de solicitudes usando Loguru."""

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import is_debug, is_testing, settings


class LoguruMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Middleware para logging de solicitudes usando Loguru."""
        request_id=request.headers.get("X-Request-ID") or str(f'desc-{uuid.uuid4()}')
        request.state.request_id = request_id

        with logger.contextualize(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "Unknown",
        ):

            start_time = time.perf_counter()
            try:
                response = await call_next(request)
                process_time = time.perf_counter() - start_time
                duration_ms = process_time * 1000

                log_message = f"{request.method} {request.url.path} | Status: {response.status_code} ({duration_ms:.2f}ms)"
                if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
                    logger.error(log_message)
                elif response.status_code >= status.HTTP_400_BAD_REQUEST:
                    logger.warning(log_message)
                else:
                    logger.info(log_message)
                response.headers["X-Request-ID"] = request_id
                return response

            except Exception as e:
                process_time = time.perf_counter() - start_time
                logger.exception(
                    f"Unhandled error | {request.method} {request.url.path} | "
                    f"Duration: {process_time*1000:.2f}ms"
                )
                raise e


class ClientValidationMiddleware(BaseHTTPMiddleware):
    """Middleware para validar el origen y cabeceras de seguridad de las peticiones.

    Asegura que las peticiones provengan únicamente del frontend oficial o que incluyan una clave
    de API secreta (para solicitudes del servidor de Next.js u otras autorizadas).
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in ["/", "/health", "/docs", "/redoc", "/openapi.json"] or path.startswith("/api/v1/health"):
            return await call_next(request)

        if is_testing or is_debug or settings.DEBUG:
            return await call_next(request)

        if origin := request.headers.get("origin"):
            clean_origin = origin.rstrip("/")
            allowed_origins = [o.rstrip("/") for o in settings.CORS_ORIGINS]
            if clean_origin not in allowed_origins:
                logger.warning(f"Acceso denegado por Origin no permitido: {origin}")
                return Response(
                    content='{"detail": "Acceso denegado: origen no permitido."}',
                    status_code=status.HTTP_403_FORBIDDEN,
                    media_type="application/json",
                )
            return await call_next(request)

        client_key = request.headers.get("X-App-Secret")
        if settings.CLIENT_API_KEY:
            if client_key != settings.CLIENT_API_KEY:
                logger.warning("Acceso denegado: llamada directa sin token de cliente válido.")
                return Response(
                    content='{"detail": "Acceso denegado: se requiere token de cliente válido."}',
                    status_code=status.HTTP_403_FORBIDDEN,
                    media_type="application/json",
                )
            return await call_next(request)

        logger.warning("Acceso denegado: llamada directa en producción sin configuración de seguridad.")
        return Response(
            content='{"detail": "Acceso denegado: las llamadas directas no están permitidas."}',
            status_code=status.HTTP_403_FORBIDDEN,
            media_type="application/json",
        )
