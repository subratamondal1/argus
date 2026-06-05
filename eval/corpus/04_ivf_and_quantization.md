# IVF and Product Quantization

Inverted file (IVF) indexing and product quantization (PQ) are two orthogonal techniques for approximate nearest-neighbor (ANN) search. IVF reduces the *number* of distance computations; PQ reduces the *cost and memory* of each stored vector. Combined as IVFPQ, they power billion-scale vector search where graph indexes like HNSW would exhaust RAM.

## IVF: Voronoi Cells and nprobe

IVF avoids scanning every vector by partitioning the dataset ahead of time. A **coarse quantizer** runs k-means to learn `nlist` centroids; each centroid owns a **Voronoi cell** — the region of space whose points are closer to that centroid than any other. Every database vector is assigned to its nearest cell, building inverted lists (centroid → member vectors).

At query time, the query is compared against the `nlist` centroids, and only the closest cells are scanned. The number of cells visited is the **nprobe** parameter (FAISS default semantics; Milvus default `nprobe=8`, range `[1, nlist]`). Small `nprobe` is fast but may miss neighbors near cell boundaries; large `nprobe` raises recall at the cost of latency. `nprobe` is a search-time knob — changing it requires no retraining. Typical `nlist` ranges from 32 to 4096 (Milvus default 128); larger `nlist` yields finer cells and better recall but slower training.

## Product Quantization

PQ compresses each D-dimensional vector independently of IVF. The vector is split into `m` equal sub-vectors of `D/m` dimensions each (`m` must divide `D`). Within each subspace, k-means learns a codebook of `k* = 2^nbits` centroids (with `nbits=8`, that is 256 centroids per subspace). Each sub-vector is replaced by the **index** of its nearest centroid, so a vector becomes `m` bytes (at 8 bits) instead of `D` floats.

The compression is dramatic: a 128-dim float32 vector occupies `128 × 32 = 4096 bits`; with `m=8, nbits=8` it shrinks to `8 × 8 = 64 bits` — a 64× reduction (~98%), the basis of the "97% less memory" headline. The implied codebook expresses an enormous number of reproduction values, `(k*)^m = 256^8 ≈ 1.8 × 10^19`, while storing only `m × 256` centroids. Distances are computed with **asymmetric distance computation (ADC)**: the query stays uncompressed, and per-subspace query-to-centroid distances are precomputed into a lookup table, so each candidate distance is `m` table lookups and adds.

## IVFPQ and the Recall–Memory Tradeoff

IVFPQ stores PQ codes *inside* IVF inverted lists: IVF prunes which lists to scan; PQ shrinks and speeds the per-vector distance. On SIFT1M, FAISS reports roughly 256 MB for an exact `IndexFlatL2` versus ~9.2 MB for `IndexIVFPQ` (~96% reduction). PQ is lossy: larger `m` and larger `nbits` preserve more accuracy but use longer codes and more memory — a tunable balance. Recall is reclaimed by raising `nprobe` (more cells scanned) and optionally re-ranking top candidates with exact distances.

## When to Prefer IVFPQ over HNSW

Choose IVFPQ when memory is the binding constraint — past ~50M to 1B+ vectors, where HNSW's requirement to store full vectors plus graph links (≈1 TB RAM at 1B vectors) becomes prohibitive. IVFPQ trades recall for a far smaller footprint and faster builds. Prefer **HNSW** when you need sub-10ms latency, recall above ~0.99, or frequent incremental updates, and the working set fits in RAM. The two also compose: using an HNSW graph as IVF's coarse quantizer accelerates the centroid-assignment step at billion scale.
