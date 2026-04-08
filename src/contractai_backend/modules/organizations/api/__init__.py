"""API package for organizations."""

from .routers.organizations_router import router as organizations_router

__all__ = ["organizations_router"]
