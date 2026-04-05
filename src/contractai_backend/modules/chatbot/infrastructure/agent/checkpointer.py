"""Checkpointer module for managing checkpoints in the chatbot agent."""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from contractai_backend.shared.config import settings


async def setup_connection(conn: AsyncConnection[DictRow]) -> None:
    """Configura la conexión a la base de datos para el checkpointer, estableciendo el search_path adecuado."""
    await conn.execute(query="SET search_path TO checkpoint, public;")


async def init_checkpointer():
    """Inicializa el checkpointer creando un pool de conexiones a la base de datos y configurando el AsyncPostgresSaver."""
    pool: AsyncConnectionPool[AsyncConnection[DictRow]] = AsyncConnectionPool(
        conninfo=settings.CONN_STRING,
        open=False,
        min_size=settings.CHECKPOINTER_POOL_MIN_SIZE,
        max_size=settings.CHECKPOINTER_POOL_MAX_SIZE,
        configure=setup_connection,
        kwargs={"prepare_threshold": 0, "row_factory": dict_row, "autocommit": True},
    )

    await pool.open()

    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()

    return pool
