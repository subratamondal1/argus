# Argus eval corpus — RAG & vector search

A curated, source-grounded knowledge corpus on **retrieval-augmented generation and
vector search**, authored as the substrate for the eval gate (`make eval`). The
golden set (`../golden.jsonl`) asks questions answerable **strictly from these
docs**; the negative cases deliberately fall *outside* this scope so a faithful
system must decline them.

## Why a curated corpus (not the repo's own docs, not random questions)

A production eval needs a **stable, version-controlled, source-grounded** corpus —
not live URLs that rot, and not made-up Q&A. Each document below was researched
against authoritative references (papers, official docs, reputable engineering
blogs) and distilled into a focused, accurate technical note. The corpus is
committed, so every `make eval` run is reproducible and offline.

## Coverage (9 documents)

| File | Topic |
|---|---|
| [`01_embeddings.md`](01_embeddings.md) | Dense embeddings, cosine/dot/L2, normalization, Matryoshka, asymmetric prefixes |
| [`02_ann_and_vector_databases.md`](02_ann_and_vector_databases.md) | Exact vs ANN, recall@k, pgvector/FAISS/Pinecone/Milvus, when ANN is needed |
| [`03_hnsw.md`](03_hnsw.md) | HNSW graph index — M, ef_construction, ef_search, tradeoffs |
| [`04_ivf_and_quantization.md`](04_ivf_and_quantization.md) | IVF, nprobe, product quantization, IVF-PQ, recall vs memory |
| [`05_lexical_bm25.md`](05_lexical_bm25.md) | TF-IDF, BM25 with k1/b, sparse/lexical retrieval |
| [`06_hybrid_search_rrf.md`](06_hybrid_search_rrf.md) | Hybrid search, Reciprocal Rank Fusion (1/(k+rank), k=60) |
| [`07_rerankers.md`](07_rerankers.md) | Bi-encoder vs cross-encoder, the retrieve-then-rerank funnel |
| [`08_chunking_contextual_retrieval.md`](08_chunking_contextual_retrieval.md) | Chunk size/overlap, Anthropic Contextual Retrieval |
| [`09_rag_architecture_and_evaluation.md`](09_rag_architecture_and_evaluation.md) | Retrieve-then-generate, faithfulness, the RAGAS quartet |

## Golden-set design (48 items)

Built to the curation best practices (diversity of type + difficulty, grounded
answers, and — critically — negative cases):

| Type | Count | What it tests |
|---|---|---|
| factual | 9 | single-doc recall |
| comparative | 10 | distinguishing two concepts |
| numerical | 12 | specific values/parameters (k=60, M, k1/b, recall@k) |
| multihop | 11 | synthesis across ≥2 docs |
| **negative** | **6** | **faithfulness — the corpus can't answer, so the system must abstain** |

Each answerable item carries `relevant_sources` (which doc should be retrieved) and
`must_include` (distinctive substrings a correct answer must contain). Every item
was **adversarially verified** by a separate pass: answerable-from-corpus, with a
correct source mapping and groundable keywords. The judge is calibrated against
`../judge_calibration.jsonl` via Cohen's κ before its verdicts may gate a build.

## Provenance

Authored from authoritative sources including the OpenAI embeddings docs, the
nomic-embed / Matryoshka and BGE model cards, the FAISS/Milvus/pgvector docs, the
BM25/Okapi literature, the Reciprocal Rank Fusion paper (Cormack et al.), Anthropic's
Contextual Retrieval post, and the RAGAS metric definitions. Per-document source
lists were captured during authoring.
