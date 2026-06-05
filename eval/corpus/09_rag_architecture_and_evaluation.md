# RAG Architecture & Evaluation

## The retrieve-then-generate pipeline

Retrieval-Augmented Generation (RAG) answers a query in two stages. First, a **retriever** fetches the top-k passages relevant to the query from an external corpus (typically via dense embedding search over a vector index, sparse search like BM25, or a hybrid of both). Second, a **generator** (an LLM) is prompted with the query plus the retrieved passages as context and produces an answer **grounded** in that context. The motivation is that the LLM's parametric memory is frozen, lossy, and unattributable; injecting fresh, source-bearing text at inference time lets the model cite specific passages and stay current without retraining.

**Grounding and citations** mean the answer is constrained to what the retrieved context supports, and spans of the answer are linked back to source passages. When the model asserts facts not present in (or contradicted by) the retrieved context, that is a **hallucination**. RAG reduces but does not eliminate hallucination: a model can still confabulate even with correct context, or the retriever can supply wrong context that the model faithfully repeats.

## Separating retrieval metrics from generation metrics

A core principle of RAG evaluation is that **retrieval quality and generation quality must be measured independently**, because a good answer can mask a bad retriever (and vice versa). Retrieval metrics require a labeled set of relevant documents per query:

- **Hit@k (hit rate)** is binary per query: 1 if at least one relevant document appears in the top-k, else 0. It is **order-unaware** — a relevant doc at rank k scores the same as at rank 1.
- **MRR (Mean Reciprocal Rank)** is **order-aware**. For each query, the reciprocal rank is `1 / (position of the first relevant document)`; if none is found, it is 0. Then `MRR = (1/N) · Σ (1/rank_i)` over N queries. Rank 1 → 1.0, rank 2 → 0.5, rank 3 → 0.333. MRR ranges 0 to 1.

The contrast: Hit@k tells you *whether* a relevant doc was retrieved; MRR additionally tells you *how highly it was ranked*.

## The RAGAS quartet

RAGAS defines four metrics, all on a 0-to-1 scale (higher is better), splitting cleanly into two generation metrics and two retrieval metrics:

- **Faithfulness** (generation): `(number of claims in the response supported by the retrieved context) / (total number of claims in the response)`. It directly measures hallucination — an unfaithful answer makes claims the context does not support.
- **Answer relevancy** (generation): the LLM reverse-engineers N artificial questions (default N=3) from the answer, then the score is the **mean cosine similarity** between each generated question's embedding and the original question's embedding: `(1/N) · Σ cos(E_gi, E_o)`. Incomplete or padded answers score lower.
- **Context precision** (retrieval): of the retrieved chunks, how many are actually useful for answering — an LLM judge returns a useful/not-useful verdict per chunk, rewarding relevant chunks ranked higher.
- **Context recall** (retrieval): `(number of claims in the reference answer supported by the retrieved context) / (total number of claims in the reference)`. It measures whether retrieval covered everything needed.

Note the symmetry: **faithfulness** checks the *answer's* claims against the context; **context recall** checks the *reference's* claims against the context.

## Reference-free LLM-judge evaluation

Three of the four RAGAS metrics — faithfulness, answer relevancy, context precision — are **reference-free**: they need no human-written gold answer, only the query, retrieved context, and generated answer, with an LLM acting as judge (e.g., decomposing answers into claims, generating questions, or scoring chunk usefulness). Only **context recall** requires a labeled reference (ground-truth answer or relevant set). This makes most of RAGAS deployable on production traffic where gold labels are unavailable, at the cost of judge variance and judge-model bias, which are typically controlled by prompt design and by validating judge scores against a small human-labeled sample.
