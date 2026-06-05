# Chunking & Contextual Retrieval

## Why chunking exists

Documents are too long to embed as a single vector and too long to fit usefully in a context window. RAG systems split documents into smaller **chunks**, embed each one, and retrieve the top-k by similarity. The chunking strategy directly bounds retrieval quality: a chunk that splits a sentence, a table, or a definition mid-thought becomes un-retrievable for queries that depend on the missing half. The two dials are **chunk size** (how many tokens per chunk) and **overlap** (how many tokens are repeated between adjacent chunks to avoid cutting context at boundaries).

## Fixed vs semantic chunking

**Fixed-size chunking** cuts on a fixed token count (e.g., 500 or 512 tokens), often with a sliding overlap. It is fast, cheap, and produces uniform, easy-to-batch chunks, but it slices through semantic units. **Recursive** splitting improves on this by preferring natural separators (paragraph → sentence → word) while respecting a size cap.

**Semantic chunking** instead uses embedding similarity to find boundaries: it embeds each sentence, computes cosine similarity between consecutive sentences, and places a chunk boundary where similarity drops below a breakpoint threshold (a commonly cited but arbitrary value is ~0.7 cosine; the right value depends on the embedding model). The cost is variable-length chunks (50 to 2000 tokens) that complicate batching, and over-fragmentation — fragments under ~100 tokens rarely carry enough context, so practitioners set a `min_chunk_size` floor (e.g., 150 tokens). Fixed-size is not strictly worse: in one February 2026 benchmark, recursive fixed splitting at 512 tokens scored 69% accuracy versus 54% for semantic chunking on general document retrieval.

## Anthropic Contextual Retrieval

A chunk loses meaning when isolated: "the company's revenue grew 3%" gives no clue which company or which quarter. **Contextual Retrieval** (Anthropic, September 2024) fixes this at ingestion time. For each chunk, an LLM is given the whole document plus the chunk and generates a short, chunk-specific context string (typically **50–100 tokens**) explaining what the chunk is about. That context is **prepended to the chunk before both the embedding step ("Contextual Embeddings") and the BM25 index ("Contextual BM25")**.

Reported failure-rate reductions on top-20-chunk retrieval:

- Contextual Embeddings alone: **35%** reduction.
- Contextual Embeddings + Contextual BM25 (hybrid): **49%** reduction.
- The above plus a reranker: **67%** reduction (failure rate **5.7% → 1.9%**).

Because the LLM re-reads the full document for every chunk, prompt caching is essential. Anthropic reports a one-time cost of about **$1.02 per million document tokens** to generate the contexts (assuming 800-token chunks, 8k-token documents, a 50-token instruction, and ~100 tokens of generated context), with prompt caching cutting latency and cost substantially.

## The classic contextualization bug

The most common implementation mistake is to **contextualize only the embedding side** — prepending the generated context to the text that gets embedded, but indexing the *raw* chunk in BM25 (or vice versa). This breaks the symmetry the technique depends on. Hybrid search fuses two ranked lists, typically with Reciprocal Rank Fusion (RRF, score = 1/(k + rank), k=60); if only one branch sees the enriched text, the keyword branch can no longer match query terms that appear only in the prepended context (the company name, the date), and the hybrid gain collapses toward the embedding-only 35% number instead of 49%. The rule is simple: the **same contextualized chunk text must feed both the dense embedding and the BM25 index**, and the reranker should also score the contextualized text. Symmetry across all three indices is what produces the full reduction.
