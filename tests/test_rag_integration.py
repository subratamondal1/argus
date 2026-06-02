"""Live ingest -> retrieve round-trip against a real Postgres+pgvector and Ollama.

Deselected by default (the `integration` marker). Run it after `make up` (data
profile) with Ollama serving nomic-embed-text:

    uv run pytest -m integration
"""

from __future__ import annotations

from pathlib import Path

import pytest

from argus.db import close_pool, get_pool
from argus.rag.ingest import ingest_source
from argus.rag.retriever import retrieve

pytestmark = pytest.mark.integration

_CORPUS: str = "argus-itest"


async def _purge() -> None:
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute("DELETE FROM chunks WHERE corpus = $1", _CORPUS)


async def test_ingest_then_retrieve_finds_the_document(tmp_path: Path) -> None:
    doc = tmp_path / "fact.md"
    doc.write_text(
        "# Argus\n\nArgus is a framework-free multi-agent deep-research engine "
        "that scales searcher pods from zero with KEDA.",
        encoding="utf-8",
    )
    try:
        await _purge()
        result = await ingest_source(str(doc), corpus=_CORPUS)
        assert result.chunks_written >= 1

        chunks = await retrieve("what scales the searcher pods?", top_k=3, corpus=_CORPUS)
        assert chunks
        assert any("KEDA" in chunk.content for chunk in chunks)
        assert chunks[0].source_uri == str(doc)
    finally:
        await _purge()
        await close_pool()
