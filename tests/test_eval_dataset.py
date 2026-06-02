from __future__ import annotations

from pathlib import Path

from argus.eval.dataset import load_golden, load_thresholds


def test_load_golden(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    path.write_text(
        '{"question":"q1","relevant_sources":["a.md"],"must_include":["x"]}\n'
        "\n"
        '{"question":"q2","relevant_sources":["b.md"]}\n',
        encoding="utf-8",
    )
    items = load_golden(path)
    assert len(items) == 2
    assert items[0].question == "q1"
    assert items[0].must_include == ["x"]
    assert items[1].must_include == []


def test_load_thresholds_applies_defaults(tmp_path: Path) -> None:
    path = tmp_path / "thresholds.json"
    path.write_text('{"k": 3, "min_hit_at_k": 0.5}', encoding="utf-8")
    thresholds = load_thresholds(path)
    assert thresholds.k == 3
    assert thresholds.min_hit_at_k == 0.5
    assert thresholds.min_mrr == 0.6
