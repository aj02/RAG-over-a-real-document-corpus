"""Database access: an async psycopg connection pool.

Why psycopg3 over asyncpg/SQLAlchemy here:
  - first-class pgvector support via the ``pgvector`` package's psycopg adapter
  - native async with low overhead and no ORM impedance mismatch
  - this codebase has only ~5 SQL touch points; a full ORM would be overkill

The pool is created at FastAPI startup and closed at shutdown. All other
modules acquire connections through ``get_pool().connection()``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from pgvector.psycopg import register_vector_async
from psycopg_pool import AsyncConnectionPool

from app.config import get_settings
from app.logging import get_logger

log = get_logger(__name__)

_pool: AsyncConnectionPool | None = None


async def _configure_connection(conn: psycopg.AsyncConnection) -> None:
    """Register the pgvector adapter on every fresh connection."""
    await register_vector_async(conn)


async def init_pool() -> AsyncConnectionPool:
    """Create the global pool. Idempotent."""
    global _pool
    if _pool is not None:
        return _pool

    settings = get_settings()
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        timeout=settings.db_timeout_seconds,
        configure=_configure_connection,
        open=False,
    )
    await pool.open(wait=True, timeout=settings.db_timeout_seconds)
    _pool = pool
    log.info("db.pool.opened", min=settings.db_pool_min, max=settings.db_pool_max)
    return pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("db.pool.closed")


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() first")
    return _pool


@asynccontextmanager
async def acquire() -> AsyncIterator[psycopg.AsyncConnection]:
    """Convenience: ``async with acquire() as conn``."""
    async with get_pool().connection() as conn:
        yield conn


async def healthcheck() -> bool:
    """Return True if the DB is reachable and the vector extension is loaded."""
    try:
        async with acquire() as conn, conn.cursor() as cur:
            await cur.execute("SELECT 1")
            row = await cur.fetchone()
            if row is None or row[0] != 1:
                return False
            await cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            return await cur.fetchone() is not None
    except Exception as e:  # noqa: BLE001
        log.warning("db.healthcheck.failed", error=str(e))
        return False
