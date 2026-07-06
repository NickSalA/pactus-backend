# ruff: noqa: E402, ARG002
"""Isolated Uvicorn runner for performance tests.

Applies dependency overrides in memory to allow GET /templates/ to run without
database or Supabase dependencies.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure src/ is in the python path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import asyncio

# Configure SelectorEventLoop on Windows for Psycopg async mode compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn
from fastapi import FastAPI

from pactus_backend import factory


# Mock init_checkpointer dynamically before calling create()
# to prevent the lifespan from attempting to connect to Postgres.
class MockPool:
    async def close(self) -> None:
        pass


async def mock_init_checkpointer() -> MockPool:
    print("Lifespan: Mocking checkpointer to skip PostgreSQL connection.")
    return MockPool()


factory.init_checkpointer = mock_init_checkpointer

from pactus_backend.modules.documents.domain import DocumentType
from pactus_backend.modules.templates.api.dependencies import get_template_service
from pactus_backend.modules.templates.application.dto import TemplateResponse
from pactus_backend.modules.templates.domain.entities import TemplateContent
from pactus_backend.modules.templates.domain.value_objs import TemplateState
from pactus_backend.modules.users.domain.entities import UserTable
from pactus_backend.modules.users.domain.value_objs import UserRole
from pactus_backend.shared.api.dependencies.security import get_current_user

app: FastAPI = factory.create()


# 1. Mock user dependency override
async def mock_get_current_user() -> UserTable:
    """Returns a static worker/admin user in memory without hitting Supabase."""
    return UserTable(
        id=1,
        organization_id=1,
        email="performance@example.com",
        full_name="Performance Test User",
        role=UserRole.ADMIN,
        is_active=True,
    )


# 2. Mock TemplateService dependency override
class MockTemplateService:
    """Mock TemplateService returning in-memory mock data to avoid PostgreSQL."""

    async def list_templates(
        self,
        organization_id: int,
        user_role: UserRole | None = None,
        document_type: DocumentType | None = None,
        format_code: str | None = None,
        state: TemplateState | None = None,
    ) -> list[TemplateResponse]:
        """Returns a static list of 3 mock templates in memory."""
        return [
            TemplateResponse(
                id=101,
                organization_id=organization_id,
                name="Contrato de Trabajo Estándar",
                description="Plantilla de prueba de rendimiento en memoria",
                document_type=DocumentType.LABOR,
                template_format_id=1,
                format_code="standard",
                format_label="Estándar",
                content=TemplateContent(
                    body_md="# Contrato de Trabajo\n\nEste es un contrato de trabajo de prueba.",
                    fields=[],
                    operational_fields=[],
                    contract_date_mapping=None,
                ),
                created_at=datetime.now(UTC),
                state=TemplateState.PUBLISHED,
            ),
            TemplateResponse(
                id=102,
                organization_id=organization_id,
                name="Acuerdo de Confidencialidad (NDA)",
                description="Segunda plantilla de prueba de rendimiento",
                document_type=DocumentType.COMPANY,
                template_format_id=2,
                format_code="nda",
                format_label="NDA",
                content=TemplateContent(
                    body_md="# Acuerdo de Confidencialidad\n\nEste es un NDA de prueba.",
                    fields=[],
                    operational_fields=[],
                    contract_date_mapping=None,
                ),
                created_at=datetime.now(UTC),
                state=TemplateState.PUBLISHED,
            ),
        ]


# Apply the overrides globally on the app instance
app.dependency_overrides[get_current_user] = mock_get_current_user
app.dependency_overrides[get_template_service] = MockTemplateService

if __name__ == "__main__":
    print("Starting isolated Performance Mock Server on port 8001...")
    uvicorn.run(app, host="127.0.0.1", port=8001)
