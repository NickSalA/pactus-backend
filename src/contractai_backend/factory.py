"""Factory module for creating and configuring the FastAPI application."""

from contextlib import asynccontextmanager
from importlib.metadata import version as get_version

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from contractai_backend.modules.integrations.api import integrations_router
from contractai_backend.modules.organizations.api import organizations_router

from .core.exceptions.base import AppError
from .modules.catalog.api.routers import router as services_router
from .modules.chatbot.api import chat_router, conversation_router
from .modules.chatbot.infrastructure.agent import init_checkpointer
from .modules.dashboard.api import dashboard_router
from .modules.documents.api.routers import router as documents_router
from .modules.documents.infrastructure import configure_embedding
from .modules.folders.api.routers import router as folders_router
from .modules.notifications.api.routers import router as notifications_router
from .modules.templates.api.routers import router as templates_router
from .modules.users.api.routers import auth_router, users_router
from .shared.api.error_handlers import app_error_handler, global_exception_handler, http_exception_handler, validation_exception_handler
from .shared.api.middlewares import LoguruMiddleware
from .shared.config import settings
from .shared.infrastructure.http import build_http_client

__version__: str = get_version(distribution_name="contractai-backend")


def create() -> FastAPI:
    """Creates and configures the FastAPI application."""

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        """Lifespan context manager for startup and shutdown events."""
        configure_embedding()
        app.state.http_client = build_http_client()
        pool = await init_checkpointer()
        app.state.pool = pool

        yield
        await app.state.http_client.aclose()
        await app.state.pool.close()

    app = FastAPI(title=settings.PROJECT_NAME, version=__version__, lifespan=lifespan)

    app.include_router(router=documents_router, prefix="/documents", tags=["Documentos"])
    app.include_router(router=services_router, prefix="/services", tags=["Servicios"])
    app.include_router(router=folders_router, prefix="/folders", tags=["Carpetas"])
    app.include_router(router=auth_router, prefix="/login", tags=["Autenticación"])
    app.include_router(router=users_router, prefix="/user", tags=["Usuarios"])
    app.include_router(router=chat_router, prefix="/chatbot", tags=["Chatbot"])
    app.include_router(router=conversation_router, prefix="/conversations", tags=["Conversaciones"])
    app.include_router(router=dashboard_router, prefix="/dashboard", tags=["Dashboard"])
    app.include_router(router=integrations_router, prefix="/integrations", tags=["Integraciones"])
    app.include_router(router=organizations_router, prefix="/organizations", tags=["Organizaciones"])
    app.include_router(router=notifications_router, prefix="/notifications", tags=["Notificaciones"])
    app.include_router(router=templates_router, prefix="/templates", tags=["Plantillas"])
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
    app.add_middleware(
        middleware_class=CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(middleware_class=LoguruMiddleware)

    app.add_exception_handler(exc_class_or_status_code=AppError, handler=app_error_handler)  # ty:ignore[invalid-argument-type]
    app.add_exception_handler(exc_class_or_status_code=StarletteHTTPException, handler=http_exception_handler)  # ty:ignore[invalid-argument-type]
    app.add_exception_handler(exc_class_or_status_code=RequestValidationError, handler=validation_exception_handler)  # ty:ignore[invalid-argument-type]
    app.add_exception_handler(exc_class_or_status_code=Exception, handler=global_exception_handler)

    @app.get(path="/")
    def home():
        """Endpoint raíz para verificar que la aplicación está funcionando."""
        return {"message": "¡Bienvenido a ContractAI-Backend!", "version": __version__}

    return app
