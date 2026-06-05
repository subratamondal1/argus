# Lexical Search & BM25

## 1. From TF-IDF to a Bag-of-Words Score

Lexical (sparse) retrieval ranks documents by the literal terms they share with a query. The classic weighting is **TF-IDF**: a term's weight rises with its frequency in a document (**term frequency, TF**) and falls with how many documents contain it (**inverse document frequency, IDF**). IDF down-weights common words like "the" and rewards rare, discriminating terms. Each document becomes a **sparse vector** over the vocabulary — most dimensions are zero — and relevance is a sum of per-term weights. The weakness of raw TF-IDF is that TF grows linearly: a term appearing 20 times scores 10x a term appearing 2 times, which over-rewards keyword stuffing and long documents.

## 2. The BM25 Ranking Function

**BM25** ("Best Matching 25") is a probabilistic ranking function from the Okapi system, developed at City University London by Stephen Robertson, Karen Spärck Jones, and collaborators; the "25" is the iteration number in their weighting series. It is the default ranking function in Lucene, Elasticsearch, and Solr.

BM25 scores a document `d` for query `Q` by summing over query terms `qᵢ`:

```
score(d, Q) = Σᵢ  IDF(qᵢ) · [ f(qᵢ,d) · (k₁ + 1) ]
                              ─────────────────────────────────────
                              f(qᵢ,d) + k₁ · (1 − b + b · |d|/avgdl)
```

where `f(qᵢ,d)` is the term frequency in the document, `|d|` is the document length, `avgdl` is the average document length in the corpus, and `IDF(qᵢ) = log( (N − nᵢ + 0.5) / (nᵢ + 0.5) + 1 )` for `N` documents and `nᵢ` documents containing the term. The `+0.5` smoothing prevents division by zero.

## 3. The k₁ and b Parameters

BM25 fixes TF-IDF's two flaws with two tunable knobs:

- **k₁ — term-frequency saturation.** It controls how fast extra occurrences of a term stop adding score. Unlike linear TF, the BM25 term factor asymptotes; higher `k₁` delays saturation (more weight to high counts), lower `k₁` saturates earlier. A typical range is 1.2–2.0; the Lucene/Elasticsearch default is **k₁ = 1.2**. At `k₁ = 0`, only IDF survives.
- **b — length normalization.** It scales the penalty for documents longer than `avgdl`. At **b = 0** length normalization is disabled (score depends only on TF and IDF); at **b = 1** it is fully applied. The default **b = 0.75** applies partial normalization, so of two documents mentioning a term equally, the shorter one scores higher.

## 4. Sparse Lexical vs. Dense Embeddings

BM25 produces **sparse vectors** keyed to exact tokens, while dense retrieval encodes meaning into low-dimensional embeddings compared by cosine/dot product.

| Property | BM25 (sparse/lexical) | Dense embeddings |
|---|---|---|
| Matching basis | Exact tokens, rare-term and identifier matching | Semantic similarity / meaning |
| Out-of-vocabulary / new terms | Handles naturally (no training) | Can miss unseen jargon, codes, names |
| Synonyms / paraphrase | Misses (vocabulary mismatch) | Strong |
| Setup cost | No training; statistics from corpus | Needs an embedding model |
| Interpretability | High (per-term contribution) | Low |

BM25 wins on exact keyword, rare-term, code/ID, name, and quote lookups, and generalizes out-of-domain because it needs no training. It fails on **vocabulary mismatch** — a colloquial query and a technical document describing the same thing with no shared tokens. Because IDF heavily weights rare words, an unusual word can pull in unrelated documents. Dense retrieval covers the synonym/paraphrase gap but can overlook exact-term hits. In practice the two are combined in **hybrid search**, often fused with Reciprocal Rank Fusion: `RRF = Σ 1/(k + rank)`, with `k = 60` a common constant.

## 5. Summary

TF-IDF introduced term weighting; BM25 adds saturated TF (via `k₁`) and tunable length normalization (via `b`), giving a sparse, training-free, interpretable scorer that excels at exact and rare-term matching and complements dense semantic retrieval.
