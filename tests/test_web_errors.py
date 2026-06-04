from __future__ import annotations

import httpx
import pytest

from argus.web import server as web


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=web.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_validation_error_uses_the_envelope() -> None:
    async with _client() as client:
        response = await client.post("/api/ask", json={"deep": False})  # missing question
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["request_id"]  # echoed from the request-id middleware


async def test_unknown_route_uses_the_envelope() -> None:
    async with _client() as client:
        response = await client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_ready_is_503_when_the_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_db() -> object:
        raise ConnectionError("could not connect to postgres")

    monkeypatch.setattr(web, "get_pool", no_db)

    async with _client() as client:
        response = await client.get("/api/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_ready"


async def test_ingest_failure_is_a_coded_422(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(source: str, *, corpus: str = "default", tenant: str = "public") -> object:
        raise ValueError("no such file")

    monkeypatch.setattr(web, "ingest_source", boom)

    async with _client() as client:
        response = await client.post("/api/ingest", json={"source": "/nope.pdf"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "unprocessable_source"
    assert "no such file" not in body["error"]["message"]  # internal detail stays in the log
