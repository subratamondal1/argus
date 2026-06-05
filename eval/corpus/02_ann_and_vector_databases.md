# ANN Search & Vector Databases

## Exact (brute-force) search vs ANN

Exact nearest-neighbor search — a "flat" or brute-force scan — compares the query vector against **every** stored vector and returns the true top-`k`. It is exact up to floating-point ties, but its cost is **O(n·d)** per query (n = corpus size, d = dimensions), which grows linearly with the corpus. At, say, 10M vectors of 1536 dimensions, a flat scan is too slow for interactive latency.

**Approximate nearest neighbor (ANN)** search trades a small, bounded amount of accuracy for large speedups by building an index (graph or partition structure) that visits only a fraction of the corpus. ANN quality is measured by **recall@k**:

```
recall@k = (# of the true top-k neighbors returned in the result's top-k) / k
```

This compares an ANN result against the brute-force ground truth. ANN never improves over exact search on accuracy — at best it ties it (recall = 1.0). Its job is to be *almost* as accurate while being far faster.

## The recall-vs-latency tradeoff (HNSW, IVF)

Every ANN index exposes knobs that move you along a recall-vs-latency curve.

**HNSW** (Hierarchical Navigable Small World), a multi-layer proximity graph, has three parameters:
- **M** — links per node. Higher M (range 12–48) improves recall and graph connectivity but increases memory (~M·8–10 bytes/element) and build time.
- **ef_construction** — candidate-list size at build time. Larger = higher index quality, slower build.
- **ef_search** — candidate-list size at query time. This is the runtime dial: e.g., on a 10M-vector set, ef_search=500 might give ~98% recall at ~5 ms, while ef_search=100 gives ~85% recall at ~1 ms.

**IVF** (Inverted File) clusters vectors into `lists` cells and searches only the `probes` nearest cells. probes=1 is fast but low recall; **setting probes = number of lists makes IVF an exact search again.** **IVF-PQ** adds Product Quantization, compressing vectors into short codes to cut memory at the cost of some recall.

## What a vector database provides

A library like **FAISS** (Meta) gives you the index structures — `IndexFlatL2` (brute-force exact), `IndexIVFFlat`, `IndexIVFPQ`, HNSW — but you manage persistence, sharding, and updates yourself. A **vector database** wraps ANN indexing with operational features: durable storage, CRUD/upserts, metadata filtering, horizontal scaling/replication, and a query API.

- **pgvector** — Postgres extension. Offers both `ivfflat` (params: `lists`, `probes`) and `hnsw` (params `m` default 16, `ef_construction` default 64, plus `ef_search`). Keeps vectors alongside relational data.
- **FAISS** — a library (not a DB): fastest raw indexing, no built-in serving layer.
- **Pinecone** — fully managed, serverless; abstracts the index away — you do **not** pick an index type or tune parameters.
- **Milvus** — open-source, distributed; offers the richest index menu: HNSW, IVF_FLAT, IVF_PQ, IVF_SQ8, **DiskANN** (stores part of the index on SSD to cut RAM for billion-scale sets).

## When is ANN actually needed?

ANN adds tuning and a recall risk, so it is not free. Rough corpus-size guidance:
- **< ~10,000 vectors** — exact brute-force is simple and fast enough; ANN is unnecessary.
- **~10K–100K** — exact still works; ANN starts to pay off.
- **up to a few million** — exact kNN can still be viable if you accept some latency.
- **> ~5M vectors** — you are firmly in ANN territory unless you tolerate high latency.

There is no single magic threshold; the crossover depends on dimensionality, latency SLA, and hardware. The discipline is: measure flat-scan latency first, and only adopt ANN once it violates your SLA — then tune ef_search / probes to hit your recall target.
