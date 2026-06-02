# ADR 0001 — Datastore: PostgreSQL + pgvector

Status: Accepted (2026-06-02)

## Context

Argus needs one local-first store for agent/research state and the contextual-RAG
vectors + lexical index. The author's cloud production system (lawworld) uses MongoDB
Atlas Vector Search. Two local options exist in 2026:

- MongoDB Community 8.2 (Sep 2025) added local `$vectorSearch`, but it requires a
  separate `mongot` search process (a JVM that defaults to ~25% of system RAM and is
  OOM-prone under mapping explosion) alongside a single-node replica set.
- PostgreSQL + pgvector runs an HNSW ANN index in-process in a single container.

Target hardware is a 24 GB Apple M4 also hosting a native Ollama model (~10 GB), which
leaves no room for a multi-GB JVM that can OOM-kill the search node.

## Decision

Use **PostgreSQL 18 + pgvector 0.8** as the single store: relational + JSONB state,
`vector(768)` embeddings (HNSW, cosine), and a `tsvector` lexical index. One container,
one async driver (asyncpg), SQL transactions across a research row and its embedding.
Do not add pgvectorscale or VectorChord — their scale advantages are irrelevant at
laptop-corpus size and both carry Apple-Silicon build/perf caveats. In Phase 5 the same
instance backs DBOS durable execution.

## Consequences

- Operational simplicity: no sidecar, no replica-set init, no JVM.
- Forfeits the tightest resume mirror (Atlas `$vectorSearch`). Framed deliberately:
  Atlas Vector Search for the cloud production system; pgvector single-store for the
  offline-capable OSS engine — chosen per context, not per fashion.
- `ts_rank` is FTS, not true BM25 (weaker IDF saturation / length normalization);
  documented upgrade path is ParadeDB `pg_search` if exact-citation recall becomes a gate.
- Claims corrected for accuracy: pgvector is not "50x faster" (that conflates
  filtered-query, index-build, and pgvectorscale-vs-Pinecone numbers) and is not itself
  "async-native" (asyncpg is the async driver; pgvector 0.8 is ~5.7-9x faster only on
  filtered queries vs 0.7.4). The real win is operational consolidation into one store.
