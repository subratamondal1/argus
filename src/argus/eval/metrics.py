"""Retrieval and judge-calibration metrics for the eval gate.

Pure and deterministic, so the eval math is unit-tested in CI with no live stack.
Retrieval functions take per-rank relevance booleans (the runner decides what is
relevant, by matching a chunk's source against the question's relevant sources),
which keeps the metric math independent of how relevance is resolved.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence


def precision_at_k(relevances: Sequence[bool], k: int) -> float:
    top: Sequence[bool] = relevances[:k]
    return sum(top) / len(top) if top else 0.0


def hit_at_k(relevances: Sequence[bool], k: int) -> float:
    return 1.0 if any(relevances[:k]) else 0.0


def reciprocal_rank(relevances: Sequence[bool]) -> float:
    for rank, relevant in enumerate(relevances, start=1):
        if relevant:
            return 1.0 / rank
    return 0.0


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def cohen_kappa(labels_a: Sequence[str], labels_b: Sequence[str]) -> float:
    if len(labels_a) != len(labels_b):
        raise ValueError("label sequences must be the same length")
    n: int = len(labels_a)
    if n == 0:
        return 0.0
    observed: float = sum(1 for a, b in zip(labels_a, labels_b, strict=True) if a == b) / n
    count_a: Counter[str] = Counter(labels_a)
    count_b: Counter[str] = Counter(labels_b)
    expected: float = sum(
        (count_a[category] / n) * (count_b[category] / n)
        for category in set(count_a) | set(count_b)
    )
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1.0 - expected)
