from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest

from argus.auth import issue_token
from argus.web import server as web


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=web.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _bearer(tenant: str = "tenant-1") -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token('u1', 'a@b.com', tenant)}"}


def test_require_tenant_rejects_anonymous() -> None:
    from argus.web.errors import ApiError

    assert web._resolve_tenant(None) == "public"
    with pytest.raises(ApiError):  # history is account-only; anonymous is rejected
        web._require_tenant(None)
    assert web._require_tenant(next(iter(_bearer("t-x").values()))) == "t-x"


async def test_history_endpoints_require_auth() -> None:
    async with _client() as client:
        for method, path in [
            ("GET", "/api/conversations"),
            ("GET", f"/api/conversations/{uuid.uuid4()}"),
            ("PUT", f"/api/conversations/{uuid.uuid4()}"),
            ("DELETE", f"/api/conversations/{uuid.uuid4()}"),
        ]:
            response = await client.request(
                method, path, json={"title": "x", "turns": []} if method == "PUT" else None
            )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"


async def test_list_returns_summaries_for_the_token_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.conversations import ConversationSummary

    seen: dict[str, str] = {}
    when = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)

    async def fake_list(tenant: str) -> list[ConversationSummary]:
        seen["tenant"] = tenant
        return [ConversationSummary("11111111-1111-1111-1111-111111111111", "RRF vs rerank", when)]

    monkeypatch.setattr(web, "list_conversations", fake_list)

    async with _client() as client:
        response = await client.get("/api/conversations", headers=_bearer("acct-9"))
    assert response.status_code == 200
    body = response.json()
    assert seen["tenant"] == "acct-9"  # scoped to the JWT's tenant, not anything client-set
    assert body["conversations"][0]["title"] == "RRF vs rerank"
    assert body["conversations"][0]["updated_at"] == int(when.timestamp() * 1000)


async def test_put_then_summary_roundtrips(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_upsert(
        tenant: str, conversation_id: str, title: str, turns: list[dict[str, object]]
    ) -> datetime:
        captured.update(tenant=tenant, id=conversation_id, title=title, turns=turns)
        return datetime(2026, 6, 4, tzinfo=UTC)

    monkeypatch.setattr(web, "upsert_conversation", fake_upsert)
    conversation_id = str(uuid.uuid4())

    async with _client() as client:
        response = await client.put(
            f"/api/conversations/{conversation_id}",
            headers=_bearer("acct-2"),
            json={"title": "My chat", "turns": [{"id": "t1", "answer": "hi"}]},
        )
    assert response.status_code == 200
    assert captured["tenant"] == "acct-2"
    assert captured["id"] == conversation_id
    assert response.json()["id"] == conversation_id


async def test_import_attaches_to_token_tenant_and_skips_junk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.conversations import ImportOutcome

    captured: dict[str, object] = {}

    async def fake_import(tenant: str, items: list[object]) -> ImportOutcome:
        captured["tenant"] = tenant
        captured["count"] = len(items)
        return ImportOutcome(len(items), 0)

    monkeypatch.setattr(web, "import_conversations", fake_import)
    body = {
        "conversations": [
            {
                "id": str(uuid.uuid4()),
                "title": "real",
                "turns": [{"id": str(uuid.uuid4()), "question": "q", "answer": "a"}],
            },
            {"id": str(uuid.uuid4()), "title": "empty", "turns": []},  # junk -> skipped
            {
                "id": str(uuid.uuid4()),
                "title": "in-progress",
                "turns": [{"id": str(uuid.uuid4()), "question": "q", "answer": "   "}],
            },  # single answer-less turn -> skipped
        ]
    }
    async with _client() as client:
        response = await client.post(
            "/api/conversations/import", headers=_bearer("acct-imp"), json=body
        )
    assert response.status_code == 200
    assert captured["tenant"] == "acct-imp"  # tenant from token, never the body
    assert captured["count"] == 1  # both junk conversations dropped before insert
    assert response.json() == {"imported": 1, "already_existed": 0, "skipped": 2}


async def test_import_requires_auth() -> None:
    async with _client() as client:
        response = await client.post("/api/conversations/import", json={"conversations": []})
    assert response.status_code == 401


async def test_import_rejects_oversized_batch() -> None:
    body = {
        "conversations": [
            {
                "id": str(uuid.uuid4()),
                "title": "t",
                "turns": [{"id": str(uuid.uuid4()), "question": "q", "answer": "a"}],
            }
            for _ in range(201)  # cap is 200
        ]
    }
    async with _client() as client:
        response = await client.post("/api/conversations/import", headers=_bearer(), json=body)
    assert response.status_code == 422


@pytest.mark.integration
async def test_import_idempotency_isolation_and_merge() -> None:
    import asyncpg

    from argus.config import get_settings
    from argus.conversations import get_conversation, import_conversations
    from argus.db import close_pool

    settings = get_settings()
    try:
        probe = await asyncpg.connect(settings.database_url)
        await probe.close()
    except Exception:
        pytest.skip(f"no Postgres at {settings.database_url}")

    alice, bob = f"alice-{uuid.uuid4().hex[:8]}", f"bob-{uuid.uuid4().hex[:8]}"
    conversation_id = uuid.uuid4()
    when = datetime(2026, 6, 4, tzinfo=UTC)
    try:
        first = await import_conversations(
            alice, [(conversation_id, "Alice", [{"id": "t1"}], when)]
        )
        assert first.imported == 1

        # Re-import with richer content -> DO NOTHING: idempotent, never clobbers.
        second = await import_conversations(
            alice, [(conversation_id, "Renamed", [{"id": "t1"}, {"id": "t2"}], when)]
        )
        assert second.imported == 0
        assert second.already_existed == 1
        survived = await get_conversation(alice, str(conversation_id))
        assert survived is not None
        assert survived.title == "Alice" and len(survived.turns) == 1  # original wins

        # Bob importing the SAME client UUID writes his own (tenant, id) row.
        await import_conversations(bob, [(conversation_id, "Bob", [{"id": "b1"}], when)])
        bob_copy = await get_conversation(bob, str(conversation_id))
        alice_copy = await get_conversation(alice, str(conversation_id))
        assert bob_copy is not None and bob_copy.title == "Bob"
        assert alice_copy is not None and alice_copy.title == "Alice"  # untouched by Bob
    finally:
        pool = await asyncpg.create_pool(settings.database_url)
        async with pool.acquire() as connection:
            await connection.execute(
                "DELETE FROM conversations WHERE tenant = ANY($1::text[])", [alice, bob]
            )
        await pool.close()
        await close_pool()


@pytest.mark.integration
async def test_history_isolation_and_roundtrip() -> None:
    import asyncpg

    from argus.config import get_settings
    from argus.conversations import (
        delete_conversation,
        get_conversation,
        list_conversations,
        upsert_conversation,
    )
    from argus.db import close_pool

    settings = get_settings()
    try:
        probe = await asyncpg.connect(settings.database_url)
        await probe.close()
    except Exception:
        pytest.skip(f"no Postgres at {settings.database_url}")

    alice, bob = f"alice-{uuid.uuid4().hex[:8]}", f"bob-{uuid.uuid4().hex[:8]}"
    conversation_id = str(uuid.uuid4())
    try:
        await upsert_conversation(alice, conversation_id, "Alice chat", [{"id": "t1", "q": "hi"}])

        # Bob cannot see Alice's conversation by id — tenant is part of the key.
        assert await get_conversation(bob, conversation_id) is None
        assert await list_conversations(bob) == []

        fetched = await get_conversation(alice, conversation_id)
        assert fetched is not None
        assert fetched.title == "Alice chat"
        assert fetched.turns == [{"id": "t1", "q": "hi"}]

        # Upsert is idempotent on (tenant, id): a second write updates in place.
        await upsert_conversation(alice, conversation_id, "Renamed", [])
        again = await get_conversation(alice, conversation_id)
        assert again is not None and again.title == "Renamed" and again.turns == []

        assert await delete_conversation(bob, conversation_id) is False  # not Bob's to delete
        assert await delete_conversation(alice, conversation_id) is True
        assert await get_conversation(alice, conversation_id) is None
    finally:
        await close_pool()
