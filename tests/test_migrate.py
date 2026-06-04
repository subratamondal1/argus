from __future__ import annotations

import pytest

from argus.migrate import run_migrations


@pytest.mark.integration
async def test_migrations_are_idempotent_and_create_the_schema() -> None:
    # Runs against a real Postgres+pgvector (CI service container / local compose);
    # skipped when none is reachable.
    import asyncpg

    from argus.config import get_settings

    settings = get_settings()
    try:
        probe = await asyncpg.connect(settings.database_url)
    except Exception:  # any connection failure means "no Postgres here"
        pytest.skip(f"no Postgres reachable at {settings.database_url}")
    await probe.close()

    await run_migrations()
    second = await run_migrations()
    assert second == []  # a second run applies nothing

    connection = await asyncpg.connect(settings.database_url)
    try:
        rows = await connection.fetch("SELECT version FROM schema_migrations")
        assert "0001_initial" in {row["version"] for row in rows}
        assert await connection.fetchval("SELECT to_regclass('public.chunks')") is not None
    finally:
        await connection.close()
