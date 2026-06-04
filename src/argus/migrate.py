"""Apply ordered SQL migrations to Postgres, tracking applied versions.

Local dev seeds the schema through the compose initdb hook, but a managed/k8s
Postgres has no such hook — so `argus migrate` (or `make migrate`) applies every
*.sql under scripts/migrations/ that has not run yet and records it in a
schema_migrations table. Each migration runs in its own transaction and
re-running is a no-op, so this is safe to run as a deploy step or k8s init job.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg

from argus.config import get_settings
from argus.logging import get_logger

log = get_logger(__name__)

MIGRATIONS_DIR: Path = Path(__file__).resolve().parents[2] / "scripts" / "migrations"

_TRACKING_TABLE: str = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def _load_migrations(folder: Path) -> list[tuple[str, str]]:
    return [(path.stem, path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.sql"))]


async def run_migrations(directory: Path | None = None) -> list[str]:
    settings = get_settings()
    migrations: list[tuple[str, str]] = _load_migrations(directory or MIGRATIONS_DIR)
    connection: asyncpg.Connection = await asyncpg.connect(settings.database_url)
    applied: list[str] = []
    try:
        await connection.execute(_TRACKING_TABLE)
        rows: list[asyncpg.Record] = await connection.fetch("SELECT version FROM schema_migrations")
        done: set[str] = {row["version"] for row in rows}
        for version, sql in migrations:
            if version in done:
                continue
            async with connection.transaction():
                await connection.execute(sql)
                await connection.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)", version
                )
            applied.append(version)
            log.info("migration_applied", version=version)
    finally:
        await connection.close()
    log.info("migrate_done", pending=len(applied), total=len(migrations))
    return applied
