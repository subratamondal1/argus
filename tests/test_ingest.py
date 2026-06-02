from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from argus.rag import ingest as ingest_mod
from argus.rag.embeddings import EMBEDDING_DIM
from argus.rag.ingest import ingest_source


async def test_context_prefix_lands_in_both_embedding_and_stored_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("# Greeting\n\nhello world\n\n## Farewell\n\ngoodbye world", encoding="utf-8")

    embedded: dict[str, list[str]] = {}
    stored: dict[str, list[str]] = {}

    async def fake_contextualize(llm: Any, *, document: str, chunk: str) -> str:
        return "CTX"

    async def fake_embed(texts: list[str], *, task: Any) -> list[list[float]]:
        embedded["texts"] = texts
        return [[0.0] * EMBEDDING_DIM for _ in texts]

    async def fake_store(
        source_uri: str,
        corpus: str,
        corpus_version: str,
        texts: list[str],
        embeddings: list[list[float]],
        embedding_model: str,
    ) -> None:
        stored["texts"] = texts

    monkeypatch.setattr(ingest_mod, "contextualize", fake_contextualize)
    monkeypatch.setattr(ingest_mod, "embed_texts", fake_embed)
    monkeypatch.setattr(ingest_mod, "_store", fake_store)

    result = await ingest_source(str(doc))

    assert result.chunks_written == 2
    # what gets embedded is exactly what gets stored (and FTS-indexed) — no
    # embed-contextualized-but-index-raw bug
    assert embedded["texts"] == stored["texts"]
    assert all(text.startswith("CTX\n\n") for text in stored["texts"])


async def test_empty_document_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = tmp_path / "empty.md"
    doc.write_text("   \n\n  ", encoding="utf-8")

    async def fail_store(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("must not store anything for an empty document")

    monkeypatch.setattr(ingest_mod, "_store", fail_store)

    result = await ingest_source(str(doc))
    assert result.chunks_written == 0
