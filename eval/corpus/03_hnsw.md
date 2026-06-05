# HNSW: Hierarchical Navigable Small World Index

HNSW is a graph-based approximate nearest neighbor (ANN) index introduced by Yury Malkov and Dmitry Yashunin in 2016 ("Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs", arXiv:1603.09320). It is the default index in many vector databases (Milvus, Qdrant, Weaviate, pgvector, FAISS) because it offers high recall at low query latency, at the cost of high memory use.

## The layered structure

HNSW organizes vectors into a multi-layer proximity graph that behaves like a probabilistic skip list. Every vector lives in layer 0 (the dense base layer); a shrinking fraction also appears in higher layers, which act as long-range "express lanes." Each node's maximum layer is drawn from an exponentially decaying distribution using `l = floor(-ln(unif(0,1)) * mL)`, where the level-normalization constant `mL = 1 / ln(M)`. This produces geometrically fewer nodes per ascending layer, the same distribution a skip list uses.

Search is greedy and top-down: it enters at a single point in the top layer, descends to the nearest neighbor found at each layer, and at layer 0 performs a beam search. Because the upper layers separate connections by distance scale, search complexity scales logarithmically, roughly O(log N) in the number of vectors N.

## The three core parameters

- **M** — the maximum number of bidirectional neighbors (edges) per node in the upper layers. Layer 0 uses a separate cap, `maxM0 = 2 * M`, because the base layer must be densely connected. Typical M is 8–48; the hnswlib default is **M = 16**. Larger M raises recall (with diminishing returns past ~16–32) and memory.
- **ef_construction** — the size of the dynamic candidate list maintained while inserting a node during the build. The hnswlib default is **200**. Higher values (e.g., 400) build a higher-quality graph and better recall but roughly double build time. It does not change index memory.
- **ef_search** (efSearch) — the size of the candidate list during a query. It must satisfy `ef_search >= k` (the number of results requested). Higher ef_search inspects more candidates, raising recall at the cost of latency. It is set per query and does not change memory.

A useful split: **M and ef_construction are fixed at build time**, while **ef_search is the cheap, runtime recall/latency knob** you tune without rebuilding.

## Memory cost

The dominant graph overhead is the neighbor lists. Each node stores up to `maxM0 = 2*M` neighbor IDs in layer 0 plus M per upper layer; with 4-byte (int32) IDs the graph costs roughly `2 * M * 4` bytes per vector, plus the raw vector itself (`d * 4` bytes for float32 of dimension d). For 768-dim float32 vectors with M=40 this is about 3,232 bytes per vector, or roughly 4.8 GB per million vectors. Memory grows with M; neither ef_construction nor ef_search affects index size.

## Recall tuning

Recall is raised by increasing M (better graph connectivity), ef_construction (better-quality build), or ef_search (deeper query-time search). The cheapest lever in production is ef_search, since it needs no rebuild. The tradeoff is concrete: in one March 2026 Redis benchmark, moving from 0.8 to 0.95 recall increased HNSW latency by roughly 31%. A common recipe is M=16, ef_construction=200, then tune ef_search per query for the target recall.
