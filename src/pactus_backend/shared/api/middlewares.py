"""Middleware personalizado para logging de solicitudes usando Loguru."""

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


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
