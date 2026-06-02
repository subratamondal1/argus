"""Hybrid retrieval: dense HNSW + lexical FTS fused with Reciprocal Rank Fusion.

One round-trip per query: the query is embedded, then a single SQL statement
runs a dense cosine-ANN scan and a lexical ts_rank_cd scan (each capped at a
candidate pool), fuses them with RRF (k=60), and returns the top-k. The HNSW
iterative-scan GUCs are set LOCAL to the transaction so they never leak across
pooled connections.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from argus.config import get_settings
from argus.db import get_pool
from argus.logging import get_logger
from argus.rag.embeddings import EmbedTask, embed_texts
from argus.rag.rerank import rerank

log = get_logger(__name__)

_EF_SEARCH: int = 100
_RERANK_POOL: int = 50

_HYBRID_SQL: str = """
WITH dense AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) AS rank
    FROM chunks
    WHERE corpus = $3
    ORDER BY embedding <=> $1::vector
    LIMIT 50
),
lexical AS (
    SELECT id, ROW_NUMBER() OVER (
               ORDER BY ts_rank_cd(tsv, websearch_to_tsquery('english', $2)) DESC
           ) AS rank
    FROM chunks
    WHERE corpus = $3
      AND tsv @@ websearch_to_tsquery('english', $2)
    LIMIT 50
),
fused AS (
    SELECT COALESCE(d.id, l.id) AS id,
           COALESCE(1.0 / (60 + d.rank), 0.0)
         + COALESCE(1.0 / (60 + l.rank), 0.0) AS score
    FROM dense d
    FULL OUTER JOIN lexical l ON d.id = l.id
)
SELECT c.source_uri, c.content, f.score
FROM fused f
JOIN chunks c ON c.id = f.id
ORDER BY f.score DESC
LIMIT $4
"""


class RetrievedChunk(BaseModel):
    content: str = Field(description="The contextualized chunk text.")
    source_uri: str = Field(description="Where the chunk was ingested from.")
    score: float = Field(description="Reciprocal-rank-fusion score (higher is better).")


async def retrieve(query: str, *, top_k: int = 5, corpus: str = "default") -> list[RetrievedChunk]:
    settings = get_settings()
    vectors: list[list[float]] = await embed_texts([query], task=EmbedTask.QUERY)
    query_vector: list[float] = vectors[0]
    fetch_k: int = _RERANK_POOL if settings.rerank_enabled else top_k

    pool = await get_pool()
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
        await connection.execute(f"SET LOCAL hnsw.ef_search = {_EF_SEARCH}")
        rows: list[Any] = await connection.fetch(_HYBRID_SQL, query_vector, query, corpus, fetch_k)

    chunks: list[RetrievedChunk] = [
        RetrievedChunk(
            content=row["content"], source_uri=row["source_uri"], score=float(row["score"])
        )
        for row in rows
    ]
    if settings.rerank_enabled and chunks:
        chunks = await _apply_rerank(query, chunks, top_k)
    log.info(
        "rag_retrieve", query=query, corpus=corpus, n=len(chunks), reranked=settings.rerank_enabled
    )
    return chunks


async def _apply_rerank(
    query: str, chunks: list[RetrievedChunk], top_k: int
) -> list[RetrievedChunk]:
    scores: list[float] = await rerank(query, [chunk.content for chunk in chunks])
    rescored: list[RetrievedChunk] = [
        chunk.model_copy(update={"score": score})
        for chunk, score in zip(chunks, scores, strict=True)
    ]
    rescored.sort(key=lambda chunk: chunk.score, reverse=True)
    return rescored[:top_k]
