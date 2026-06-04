"""The ingest pipeline: parse -> chunk -> contextual prefix -> embed -> store.

The contextual prefix is prepended to each chunk BEFORE both the embedding and
the tsvector are built, so dense and lexical retrieval see the same
contextualized text. Re-ingesting a source replaces its existing chunks, so the
operation is idempotent per (source, corpus, corpus_version).
"""

from __future__ import annotations

from dataclasses import dataclass

from argus.config import get_settings
from argus.db import get_pool
from argus.llm import LLMClient
from argus.logging import get_logger
from argus.rag.chunking import chunk_markdown
from argus.rag.context import contextualize
from argus.rag.embeddings import EmbedTask, embed_texts
from argus.rag.parse import parse_source

log = get_logger(__name__)

_DELETE: str = (
    "DELETE FROM chunks "
    "WHERE source_uri = $1 AND corpus = $2 AND corpus_version = $3 AND tenant = $4"
)
_INSERT: str = (
    "INSERT INTO chunks "
    "(corpus, corpus_version, source_uri, content, embedding, tsv, embedding_model, tenant) "
    "VALUES ($1, $2, $3, $4, $5, to_tsvector('english', $4), $6, $7)"
)


@dataclass(frozen=True)
class IngestResult:
    source_uri: str
    chunks_written: int


async def ingest_source(
    source: str, *, corpus: str = "default", corpus_version: str = "v1", tenant: str = "public"
) -> IngestResult:
    settings = get_settings()
    parsed = await parse_source(source)
    chunks: list[str] = chunk_markdown(parsed.markdown)
    if not chunks:
        log.warning("ingest_empty", source=parsed.uri)
        return IngestResult(source_uri=parsed.uri, chunks_written=0)

    llm = LLMClient(
        model=settings.context_model or settings.model, timeout_s=settings.request_timeout_s
    )
    contextualized: list[str] = []
    for chunk in chunks:
        context: str = await contextualize(llm, document=parsed.markdown, chunk=chunk)
        contextualized.append(f"{context}\n\n{chunk}" if context else chunk)

    embeddings: list[list[float]] = await embed_texts(contextualized, task=EmbedTask.DOCUMENT)
    await _store(
        parsed.uri,
        corpus,
        corpus_version,
        contextualized,
        embeddings,
        settings.embedding_model,
        tenant,
    )
    log.info("ingest", source=parsed.uri, chunks=len(chunks), tenant=tenant)
    return IngestResult(source_uri=parsed.uri, chunks_written=len(chunks))


async def _store(
    source_uri: str,
    corpus: str,
    corpus_version: str,
    texts: list[str],
    embeddings: list[list[float]],
    embedding_model: str,
    tenant: str,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute(_DELETE, source_uri, corpus, corpus_version, tenant)
        await connection.executemany(
            _INSERT,
            [
                (corpus, corpus_version, source_uri, text, embedding, embedding_model, tenant)
                for text, embedding in zip(texts, embeddings, strict=True)
            ],
        )
