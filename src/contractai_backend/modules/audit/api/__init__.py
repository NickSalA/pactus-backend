"""Audit API exports."""

from fastapi import APIRouter

from .routers.ai_token_usage_router import router as ai_token_usage_router
from .routers.chatbot_activity_router import router as chatbot_activity_router
from .routers.contract_activity_router import router as contract_activity_router
from .routers.template_activity_router import router as template_activity_router
from .routers.user_activity_router import router as user_activity_router

audit_router = APIRouter()
audit_router.include_router(user_activity_router)
audit_router.include_router(chatbot_activity_router)
audit_router.include_router(template_activity_router)
audit_router.include_router(contract_activity_router)
audit_router.include_router(ai_token_usage_router)

__all__ = ["audit_router"]
