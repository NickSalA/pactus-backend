"""API package for dashboard endpoints."""

__all__ = ["dashboard_router"]


def __getattr__(name: str):
    if name == "dashboard_router":
        from .routers import router as dashboard_router

        return dashboard_router
    raise AttributeError(name)
