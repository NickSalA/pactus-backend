"""Integration fixtures for dashboard PostgreSQL read-model tests."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.dashboard.infrastructure.postgres_repo import SQLModelDashboardRepository

TEST_DATABASE_URL = "postgresql+asyncpg://contractai_test:contractai_test@localhost:5433/contractai_test"


@pytest.fixture(scope="session")
async def dashboard_test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("select 1"))
            schema_sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
            await conn.exec_driver_sql(schema_sql)
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL de prueba no disponible en localhost:5433: {exc}")

    yield engine
    await engine.dispose()


@pytest.fixture
async def dashboard_session(dashboard_test_engine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(bind=dashboard_test_engine, expire_on_commit=False) as session:
        await session.exec(text("truncate table documents_services, documents, services restart identity"))
        await session.commit()
        yield session
        await session.rollback()
        await session.exec(text("truncate table documents_services, documents, services restart identity"))
        await session.commit()


@pytest.fixture
def dashboard_repo(dashboard_session: AsyncSession) -> SQLModelDashboardRepository:
    return SQLModelDashboardRepository(session=dashboard_session)
