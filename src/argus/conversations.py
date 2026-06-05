"""Server-side conversation history, isolated per tenant.

A conversation's turns are stored as a JSONB blob keyed by (tenant, id) — the
tenant is part of the primary key, so a conversation can never be read or written
across the tenant boundary by id alone. The shape of a turn is owned by the web UI
(question, answer, sources, ...); this layer treats it as opaque JSON and only
guarantees isolation, ordering, and updated_at bookkeeping. Anonymous users keep
their history in the browser; only authenticated tenants reach this store.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import orjson

from argus.db import get_pool

_LIST_LIMIT: int = 200


@dataclass(frozen=True)
class ConversationSummary:
    id: str
    title: str
    updated_at: datetime


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    updated_at: datetime
    turns: list[dict[str, Any]]


@dataclass(frozen=True)
class ImportOutcome:
    imported: int
    already_existed: int


async def list_conversations(tenant: str) -> list[ConversationSummary]:
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT id::text AS id, title, updated_at FROM conversations "
            "WHERE tenant = $1 ORDER BY updated_at DESC LIMIT $2",
            tenant,
            _LIST_LIMIT,
        )
    return [ConversationSummary(row["id"], row["title"], row["updated_at"]) for row in rows]


async def get_conversation(tenant: str, conversation_id: str) -> Conversation | None:
    key: uuid.UUID | None = _as_uuid(conversation_id)
    if key is None:
        return None
    pool = await get_pool()
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            "SELECT id::text AS id, title, updated_at, turns FROM conversations "
            "WHERE tenant = $1 AND id = $2",
            tenant,
            key,
        )
    if row is None:
        return None
    return Conversation(row["id"], row["title"], row["updated_at"], orjson.loads(row["turns"]))


async def upsert_conversation(
    tenant: str, conversation_id: str, title: str, turns: list[dict[str, Any]]
) -> datetime | None:
    key: uuid.UUID | None = _as_uuid(conversation_id)
    if key is None:
        return None
    pool = await get_pool()
    async with pool.acquire() as connection:
        updated_at: datetime = await connection.fetchval(
            "INSERT INTO conversations (id, tenant, title, turns) VALUES ($1, $2, $3, $4::jsonb) "
            "ON CONFLICT (tenant, id) DO UPDATE "
            "SET title = EXCLUDED.title, turns = EXCLUDED.turns, updated_at = now() "
            "RETURNING updated_at",
            key,
            tenant,
            title,
            orjson.dumps(turns).decode(),
        )
    return updated_at


async def import_conversations(
    tenant: str, items: list[tuple[uuid.UUID, str, list[dict[str, Any]], datetime]]
) -> ImportOutcome:
    # Adopt the anonymous chats a user uploads at signup/login. ON CONFLICT DO
    # NOTHING is deliberate (unlike the live-save upsert's DO UPDATE): importing a
    # stale local copy must never clobber richer server history — it only adds the
    # conversations the account doesn't have yet. Idempotent: the client UUID is the
    # key, so re-running converges. The whole batch is one transaction.
    if not items:
        return ImportOutcome(0, 0)
    pool = await get_pool()
    imported: int = 0
    async with pool.acquire() as connection, connection.transaction():
        for conversation_id, title, turns, created_at in items:
            tag: str = await connection.execute(
                "INSERT INTO conversations (id, tenant, title, turns, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4::jsonb, $5, $5) "
                "ON CONFLICT (tenant, id) DO NOTHING",
                conversation_id,
                tenant,
                title,
                orjson.dumps(turns).decode(),
                created_at,
            )
            if tag.endswith("1"):
                imported += 1
    return ImportOutcome(imported, len(items) - imported)


async def delete_conversation(tenant: str, conversation_id: str) -> bool:
    key: uuid.UUID | None = _as_uuid(conversation_id)
    if key is None:
        return False
    pool = await get_pool()
    async with pool.acquire() as connection:
        result: str = await connection.execute(
            "DELETE FROM conversations WHERE tenant = $1 AND id = $2", tenant, key
        )
    return result.endswith("1")


def _as_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
