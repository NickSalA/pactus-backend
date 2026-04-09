"""Database configuration and session management for ContractAI Backend."""

import ssl
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from typing import Literal

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from contractai_backend.shared.config import settings

DATABASE_URL: str = settings.DATABASE_URL
parsed_database_url = urlparse(DATABASE_URL)

connect_args = {}
if DATABASE_URL and "localhost" not in DATABASE_URL:
    ctx: ssl.SSLContext = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode: Literal[ssl.VerifyMode.CERT_NONE] = ssl.CERT_NONE
    connect_args: dict[str, ssl.SSLContext] = {"ssl": ctx}

# Supavisor transaction mode does not support prepared statements.
if parsed_database_url.port == 6543 and parsed_database_url.hostname and parsed_database_url.hostname.endswith(".pooler.supabase.com"):
    connect_args["statement_cache_size"] = 0

engine: AsyncEngine = create_async_engine(
    url=DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    connect_args=connect_args,
)


async def get_session():
    """Proporciona una sesión de base de datos asíncrona."""
    async with AsyncSession(bind=engine, expire_on_commit=False) as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


get_session_context = asynccontextmanager(get_session)
