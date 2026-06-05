# Cross-Encoder Rerankers

## The bi-encoder / cross-encoder split

A **bi-encoder** (e.g. a sentence-transformer) embeds the query and each document *independently* into fixed-length vectors, then scores them with a cheap similarity like cosine. Because document vectors are computed once and indexed, retrieval at query time is a vector lookup over an ANN index (HNSW, IVF) — sublinear in corpus size. The cost is accuracy: the query and document never "see" each other, so fine-grained term interactions are lost.

A **cross-encoder** takes the opposite design. It concatenates the query and one document into a single input (`[CLS] query [SEP] document [SEP]`), runs the full transformer over the pair, and emits a *single relevance logit* from the pooled/`[CLS]` representation (passed through a sigmoid to map to [0,1] if a probability is wanted). Full cross-attention between query and document tokens makes it markedly more accurate — but it produces **no reusable embedding**. Every (query, document) pair must be run through the network at query time.

## Why you never cross-encode the whole corpus

Because a cross-encoder cannot precompute document representations, scoring a query against `N` documents costs `N` forward passes — the work is **O(candidates)**, linear in how many documents you score. Over a corpus of millions, that is impossible to do per query within any latency budget. The standard solution is the **retrieve-then-rerank funnel**:

1. **First stage (recall):** a fast bi-encoder (or BM25, with parameters `k1` and `b`) over an ANN index returns a wide candidate pool — typically the top 50–200 documents.
2. **Second stage (precision):** the cross-encoder scores *only those candidates* and re-sorts them, narrowing to a small working set (often 3–10) that becomes the LLM context.

A common configuration is N=50 → K=5 (roughly a 10:1 ratio). The cross-encoder's latency is proportional to the candidate-pool size, so the pool count `N` directly trades accuracy (higher recall) against cost. The reranker's value is also proportional to that pool: it can only re-order what the first stage retrieved — it cannot recover a document that recall missed.

## Production reranker models

| Model | Type | Key facts |
|---|---|---|
| `cross-encoder/ms-marco-MiniLM-L6-v2` | Open, 6-layer MiniLM | Trained on MS MARCO passage ranking; outputs one logit per query-passage pair. |
| `BAAI/bge-reranker-v2-m3` | Open, multilingual | 568M parameters, ~2.27 GB; built on bge-m3; max input 512 tokens; supports FP16/BF16. |
| Cohere `rerank-v3.5` | Hosted API | 4096-token context; query truncated to 2048 tokens; `max_tokens_per_doc` default 4096; max 10,000 documents per request (≤1,000 recommended for performance). |

All three are pairwise scorers: you send a query plus a list of candidate documents and get back relevance scores to sort by. The open models run locally on GPU and are efficient when candidates are **batched**; scoring one-by-one spikes latency. The hosted API trades self-hosting for a per-call charge.

## Operating-point notes

The funnel exposes two knobs. Raising `N` (candidate pool) raises recall but linearly raises rerank latency and cost. Lowering `K` (kept after rerank) shrinks the context the LLM must read. Cross-encoders are accurate but throughput-bound, so they belong only on a *pruned* candidate set, never on the corpus — exactly the inversion that makes the two-stage design work: a fast, recall-oriented retriever feeding a slow, precision-oriented reranker.
