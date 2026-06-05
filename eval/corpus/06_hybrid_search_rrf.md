# Hybrid Search and Reciprocal Rank Fusion

## The problem: two retrievers with incompatible scores

Dense (vector/embedding) retrieval and lexical retrieval (BM25) fail and succeed on different queries. Dense retrieval captures semantic similarity — it matches paraphrases, synonyms, and conceptual overlap even when no words match. Lexical BM25 captures exact-term overlap and excels on rare tokens, identifiers, codes, and proper nouns that embeddings often smear together. Each retriever alone leaves recall on the table; hybrid search runs both and fuses their result lists into one ranking, so a document that either retriever ranks highly survives.

The obstacle is that the two scores live on incompatible scales. BM25 produces unbounded, corpus-dependent term-weight sums (driven by parameters `k1`, default ≈1.2, controlling term-frequency saturation, and `b`, default ≈0.75, controlling document-length normalization). Dense scores are cosine similarities in `[-1, 1]` or inner products with a totally different distribution. Adding raw scores lets whichever retriever has the larger numeric range dominate, regardless of actual relevance.

## Reciprocal Rank Fusion: rank-based, scale-free

Reciprocal Rank Fusion (RRF), introduced by Cormack, Clarke, and Büttcher (SIGIR 2009, "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods"), sidesteps the scale problem entirely by discarding scores and using only rank position. For a document `d` appearing across result lists, its fused score is:

```
RRF_score(d) = Σ over lists i  of  1 / (k + rank_i(d))
```

where `rank_i(d)` is `d`'s 1-indexed position in list `i` (top result = rank 1), and `k` is a constant conventionally set to **k = 60** (the value from the original paper). Documents absent from a list contribute 0 for that list.

Because only ranks enter the formula, RRF needs **no score normalization** — it is immune to the BM25-vs-cosine scale mismatch by construction. The constant `k` dampens the influence of the very top ranks: with k = 60, the gap between rank 1 (1/61 ≈ 0.0164) and rank 2 (1/62 ≈ 0.0161) is small (~1.6% relative), so no single list can unilaterally dominate, and agreement across lists is rewarded. A larger `k` flattens the curve further (more weight to deep ranks); a smaller `k` sharpens the advantage of top ranks.

## Convex combination: the score-based alternative

The alternative family is convex (linear) combination: `score = α · norm(dense) + (1 − α) · norm(lexical)`, with `α ∈ [0, 1]`. This requires normalizing each retriever's scores first — commonly min-max or z-score (standard-score) normalization — to a comparable range before the weighted average. Bruch et al., "An Analysis of Fusion Functions for Hybrid Retrieval" (ACM TOIS, 2023), found that a tuned convex combination outperforms RRF both in-domain and out-of-domain, that its ranking is largely agnostic to the choice of linear normalization (min-max, z-score, etc. are rank-equivalent under suitable convex weights), and that it is sample-efficient — only its single weight needs tuning. The same work notes a tuned RRF generalizes poorly out-of-domain. The tradeoff: RRF is robust and zero-configuration; convex combination has higher accuracy ceiling but needs normalization and a tuned weight per domain.

## Why hybrid beats either retriever alone

Hybrid wins because the two retrievers' errors are weakly correlated. BM25 misses semantic matches with no lexical overlap; dense retrieval misses exact rare-token matches it cannot embed distinctly. Fusing recovers documents each would have dropped, so a relevant result needs to be found by only one retriever to enter the candidate pool, and consensus across both promotes it. RRF (k = 60) is the common default in Elasticsearch and OpenSearch precisely because it delivers this lift with no per-corpus calibration.
