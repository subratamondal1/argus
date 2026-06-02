from __future__ import annotations

import pytest

from argus.eval.metrics import cohen_kappa, hit_at_k, mean, precision_at_k, reciprocal_rank


def test_precision_at_k() -> None:
    assert precision_at_k([True, False, True, False], 4) == 0.5
    assert precision_at_k([True, True], 4) == 1.0
    assert precision_at_k([], 4) == 0.0
    assert precision_at_k([False, False, True], 2) == 0.0


def test_hit_at_k() -> None:
    assert hit_at_k([False, False, True], 2) == 0.0
    assert hit_at_k([False, True], 2) == 1.0
    assert hit_at_k([], 5) == 0.0


def test_reciprocal_rank() -> None:
    assert reciprocal_rank([False, False, True]) == pytest.approx(1 / 3)
    assert reciprocal_rank([True]) == 1.0
    assert reciprocal_rank([False, False]) == 0.0


def test_mean() -> None:
    assert mean([1.0, 2.0, 3.0]) == 2.0
    assert mean([]) == 0.0


def test_cohen_kappa() -> None:
    assert cohen_kappa(["p", "p", "f"], ["p", "p", "f"]) == 1.0
    # 3/4 observed agreement, 0.5 expected by chance -> kappa 0.5
    assert cohen_kappa(["p", "p", "f", "f"], ["p", "f", "f", "f"]) == pytest.approx(0.5)
    assert cohen_kappa([], []) == 0.0


def test_cohen_kappa_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        cohen_kappa(["p"], ["p", "f"])
