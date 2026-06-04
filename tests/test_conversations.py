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
