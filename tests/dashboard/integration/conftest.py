"""Integration fixtures for dashboard repository tests."""

from collections.abc import AsyncIterator
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import text
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.modules.dashboard.infrastructure.postgres_repo import SQLModelDashboardRepository


def _async_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
async def dashboard_engine():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(_async_database_url(TEST_DATABASE_URL), poolclass=NullPool)
    schema_name = f"dashboard_test_{uuid4().hex}"
    schema_sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")

    async with engine.begin() as connection:
        await connection.execute(text(f'create schema "{schema_name}"'))
        await connection.execute(text(f'set search_path to "{schema_name}"'))
        for statement in schema_sql.split(";"):
            if statement.strip():
                await connection.execute(text(statement))

    try:
        yield engine, schema_name
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'drop schema if exists "{schema_name}" cascade'))
        await engine.dispose()


@pytest.fixture
async def dashboard_session(dashboard_engine) -> AsyncIterator[AsyncSession]:
    engine, schema_name = dashboard_engine
    async with AsyncSession(engine) as session:
        await session.exec(text(f'set search_path to "{schema_name}"'))
        yield session
        await session.rollback()


@pytest.fixture
def dashboard_repo(dashboard_session: AsyncSession) -> SQLModelDashboardRepository:
    return SQLModelDashboardRepository(session=dashboard_session)
