from __future__ import annotations

import pytest

from argus.rag import retriever as retriever_mod
from argus.rag.rerank import rerank
from argus.rag.retriever import RetrievedChunk, _apply_rerank


async def test_empty_passages_never_load_the_model() -> None:
    assert await rerank("q", []) == []


async def test_rerank_reorders_by_cross_encoder_score(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = [
        RetrievedChunk(content="weak first-stage match", source_uri="a.md", score=0.9),
        RetrievedChunk(content="strong cross-encoder match", source_uri="b.md", score=0.1),
    ]

    async def fake_rerank(query: str, passages: list[str]) -> list[float]:
        return [0.02 if "weak" in passage else 0.98 for passage in passages]

    monkeypatch.setattr(retriever_mod, "rerank", fake_rerank)
    reranked = await _apply_rerank("q", chunks, top_k=5)

    assert [chunk.source_uri for chunk in reranked] == ["b.md", "a.md"]
    assert reranked[0].score == pytest.approx(0.98)


async def test_rerank_truncates_to_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    chunks = [RetrievedChunk(content=f"c{i}", source_uri=f"{i}.md", score=0.0) for i in range(10)]

    async def fake_rerank(query: str, passages: list[str]) -> list[float]:
        return [float(len(passages) - i) for i in range(len(passages))]

    monkeypatch.setattr(retriever_mod, "rerank", fake_rerank)
    reranked = await _apply_rerank("q", chunks, top_k=3)

    assert len(reranked) == 3
    assert [chunk.source_uri for chunk in reranked] == ["0.md", "1.md", "2.md"]
