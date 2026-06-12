"""Audit API exports."""

from fastapi import APIRouter

from .routers.chatbot_activity_router import router as chatbot_activity_router
from .routers.template_activity_router import router as template_activity_router
from .routers.user_activity_router import router as user_activity_router

audit_router = APIRouter()
audit_router.include_router(user_activity_router)
audit_router.include_router(chatbot_activity_router)
audit_router.include_router(template_activity_router)

__all__ = ["audit_router"]
