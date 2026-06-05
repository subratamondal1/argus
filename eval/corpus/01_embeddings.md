# Embeddings & Semantic Similarity

## Why dense embeddings exist

A dense embedding maps a piece of text to a fixed-length vector of floating-point numbers (e.g. 768 or 1536 values) such that texts with similar meaning land near each other in vector space. Unlike sparse lexical methods (BM25, TF-IDF), which match on exact terms, dense embeddings capture *semantic* similarity: "car" and "automobile" can be close even with no shared tokens. Retrieval becomes a nearest-neighbor search over these vectors, typically accelerated by an approximate index such as HNSW or IVF.

## Similarity metrics: cosine vs dot product vs Euclidean

Three metrics dominate:

- **Cosine similarity** measures the angle between two vectors, ignoring magnitude: `cos(θ) = (A · B) / (‖A‖ ‖B‖)`, ranging from −1 to 1.
- **Dot product** is `A · B = Σ Aᵢ Bᵢ`. It is sensitive to magnitude.
- **Euclidean (L2) distance** is `√(Σ (Aᵢ − Bᵢ)²)`; smaller means more similar.

The key identity: for **L2-normalized** vectors (unit length, ‖A‖ = ‖B‖ = 1), cosine similarity *equals* the dot product, because `A · B = ‖A‖ ‖B‖ cos(θ) = cos(θ)`. For normalized vectors, cosine, dot product, and Euclidean distance all produce the **same ranking** (Euclidean distance² = 2 − 2·cos(θ)). In practice, normalize once and use dot product, which is slightly faster than computing cosine at query time. Use raw dot product only when magnitude carries signal and the model was trained for it.

## Normalization

L2 normalization divides each vector by its norm so every vector sits on the unit hypersphere. This makes magnitude irrelevant and lets you swap metrics freely. OpenAI's text-embedding-3 models return normalized embeddings, so dot product and cosine give identical rankings. If you mix normalized and unnormalized vectors in one index, similarity scores become meaningless — normalize consistently at both index and query time.

## Embedding models

Representative models and their native dimensionality:

| Model | Dimensions | Notes |
|---|---|---|
| nomic-embed-text-v1.5 | 768 (truncatable to 64) | 8192-token context; Matryoshka training |
| text-embedding-3-small | 1536 | shortenable via `dimensions` param |
| text-embedding-3-large | 3072 | MTEB ~64.6%; can shorten to 256 |
| bge-large-en-v1.5 | 1024 | requires query instruction prefix |

**Matryoshka Representation Learning** (used by nomic-embed-text-v1.5 and OpenAI v3) trains nested representations so a vector can be truncated to a shorter prefix (e.g. 768 → 256) and still rank well, trading a little accuracy for less memory. On MTEB, a text-embedding-3-large vector truncated to 256 dims still outperforms a full 1536-dim ada-002 vector. text-embedding-3-small scores 62.3% on MTEB vs ada-002's 61.0%.

## Symmetric vs asymmetric embeddings

- **Symmetric** tasks (sentence similarity, deduplication, clustering) compare two texts of the same kind; queries and documents are embedded identically.
- **Asymmetric** retrieval matches a short query against a long document. Several models inject a **task prefix** so the model knows the role. nomic-embed-text uses `search_query:` for queries and `search_document:` for documents. bge models prepend `"Represent this sentence for searching relevant passages:"` to queries only, leaving documents unprefixed.

Using the wrong prefix (or none) silently degrades recall, because the query and document vectors land in mismatched regions of the space. The prefix convention is a *training detail* of the specific model — always check the model card, because it is not interchangeable across model families.
