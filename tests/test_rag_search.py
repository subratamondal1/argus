from __future__ import annotations

from typing import Any

import pytest

from argus.rag.retriever import RetrievedChunk
from argus.tools import rag_search as rag_search_mod
from argus.tools.rag_search import register_rag_search
from argus.tools.registry import Permission, ToolCall, ToolRegistry


def _registry(monkeypatch: pytest.MonkeyPatch, chunks: list[RetrievedChunk]) -> ToolRegistry:
    async def fake_retrieve(
        query: str, *, top_k: int = 5, corpus: str = "default", tenant: str = "public"
    ) -> list[Any]:
        return chunks[:top_k]

    monkeypatch.setattr(rag_search_mod, "retrieve", fake_retrieve)
    registry = ToolRegistry()
    register_rag_search(registry)
    return registry


async def test_returns_retrieved_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = [
        RetrievedChunk(content="alpha", source_uri="a.md", score=0.9),
        RetrievedChunk(content="beta", source_uri="b.md", score=0.5),
    ]
    registry = _registry(monkeypatch, chunks)
    result = await registry.dispatch(
        ToolCall(name="rag_search", arguments={"query": "x", "top_k": 5})
    )
    assert result.ok
    assert result.content.query == "x"
    assert [chunk.content for chunk in result.content.chunks] == ["alpha", "beta"]
    assert result.content.chunks[0].source_uri == "a.md"


async def test_respects_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = [
        RetrievedChunk(content=f"c{i}", source_uri=f"{i}.md", score=1.0 / (i + 1))
        for i in range(10)
    ]
    registry = _registry(monkeypatch, chunks)
    result = await registry.dispatch(
        ToolCall(name="rag_search", arguments={"query": "x", "top_k": 3})
    )
    assert result.ok
    assert len(result.content.chunks) == 3


def test_registered_as_an_allowed_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _registry(monkeypatch, [])
    tool = registry.get("rag_search")
    assert tool is not None
    assert tool.permission is Permission.ALLOW
    assert "rag_search" in [entry["function"]["name"] for entry in registry.schema()]
