"""Async PostgreSQL connection pool with pgvector type registration.

register_vector must run on every pooled connection (via the pool init callback),
or list/array vector parameters serialize as plain text and queries fail.
"""

from __future__ import annotations

import asyncpg
from pgvector.asyncpg import register_vector

from argus.config import get_settings
from argus.logging import get_logger

log = get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def _init_connection(connection: asyncpg.Connection) -> None:
    await register_vector(connection)


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            settings.database_url,
            init=_init_connection,
            min_size=1,
            max_size=8,
        )
        log.info("db_pool_open", dsn=_safe_dsn(settings.database_url))
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("db_pool_closed")


def _safe_dsn(dsn: str) -> str:
    at_marker: int = dsn.rfind("@")
    if at_marker == -1:
        return dsn
    scheme_end: int = dsn.find("://")
    prefix: str = dsn[: scheme_end + 3] if scheme_end != -1 else ""
    return f"{prefix}***@{dsn[at_marker + 1 :]}"
