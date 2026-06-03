from __future__ import annotations

from typing import Any

import httpx
import orjson
import pytest

from argus.agent.events import AgentEvent
from argus.agent.orchestrator import ResearchReport
from argus.web import server as web


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=web.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_health() -> None:
    async with _client() as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


class _FakeAdaptive:
    async def run(
        self, question: str, *, on_event: Any = None, force_research: bool = False
    ) -> ResearchReport:
        if on_event is not None:
            await on_event(AgentEvent("triage", {"strategy": "direct", "reasoning": "simple"}))
            await on_event(AgentEvent("turn", {"n": 1, "tool_calls": 1}))
            await on_event(AgentEvent("tool", {"name": "rag_search", "query": question}))
            await on_event(AgentEvent("token", {"text": "the "}))
            await on_event(AgentEvent("token", {"text": "answer"}))
            await on_event(AgentEvent("answer", {"text": "the grounded answer"}))
        return ResearchReport(
            question=question, answer="the grounded answer", findings=[], rounds=0
        )


async def test_ask_streams_progress_then_answer_then_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web, "build_adaptive", lambda *_args, **_kwargs: _FakeAdaptive())

    async def fake_related(question: str, answer: str) -> list[str]:
        return ["a follow-up question?"]

    monkeypatch.setattr(web, "_related_questions", fake_related)

    events: list[dict[str, Any]] = []
    async with (
        _client() as client,
        client.stream(
            "POST", "/api/ask", json={"question": "what is argus", "deep": False}
        ) as response,
    ):
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                events.append(orjson.loads(line[len("data:") :].strip()))

    kinds = [event["type"] for event in events]
    assert "triage" in kinds
    assert "turn" in kinds
    assert "tool" in kinds
    assert "token" in kinds
    assert "answer" in kinds
    assert "related" in kinds
    assert kinds[-1] == "done"
    answer = next(event for event in events if event["type"] == "answer")
    assert answer["text"] == "the grounded answer"


async def test_ingest_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Result:
        source_uri = "README.md"
        chunks_written = 7

    async def fake_ingest(source: str, *, corpus: str = "default") -> Any:
        return _Result()

    monkeypatch.setattr(web, "ingest_source", fake_ingest)

    async with _client() as client:
        response = await client.post("/api/ingest", json={"source": "README.md"})
    assert response.status_code == 200
    assert response.json() == {"source_uri": "README.md", "chunks_written": 7}


async def test_ingest_upload_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Result:
        source_uri = "ignored"
        chunks_written = 3

    async def fake_ingest(source: str, *, corpus: str = "default") -> Any:
        return _Result()

    monkeypatch.setattr(web, "ingest_source", fake_ingest)

    async with _client() as client:
        response = await client.post(
            "/api/ingest/upload",
            files={"file": ("notes.md", b"# hi\n\nbody", "text/markdown")},
        )
    assert response.status_code == 200
    assert response.json() == {"source_uri": "notes.md", "chunks_written": 3}
