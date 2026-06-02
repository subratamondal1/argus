from __future__ import annotations

from argus.eval.calibration import calibrate
from argus.eval.dataset import CalibrationItem
from argus.eval.judge import Verdict


def _items() -> list[CalibrationItem]:
    return [
        CalibrationItem(question="q1", answer="a1", context="c1", label="pass"),
        CalibrationItem(question="q2", answer="a2", context="c2", label="fail"),
        CalibrationItem(question="q3", answer="a3", context="c3", label="pass"),
        CalibrationItem(question="q4", answer="a4", context="c4", label="fail"),
    ]


async def test_a_perfect_judge_has_kappa_one() -> None:
    items = _items()
    truth = {item.question: item.label for item in items}

    async def judge(question: str, answer: str, context: str) -> Verdict:
        return Verdict(passed=truth[question] == "pass", reason="")

    result = await calibrate(items, judge=judge, min_kappa=0.6)
    assert result.kappa == 1.0
    assert result.agreement == 1.0
    assert result.passed
    assert result.disagreements == []


async def test_kappa_exposes_a_rubber_stamp_judge() -> None:
    items = _items()

    async def always_pass(question: str, answer: str, context: str) -> Verdict:
        return Verdict(passed=True, reason="")

    result = await calibrate(items, judge=always_pass, min_kappa=0.6)
    # raw agreement is a deceptive 0.5, but chance-corrected kappa is 0.0 — the
    # judge is no better than chance, and calibration fails.
    assert result.agreement == 0.5
    assert result.kappa == 0.0
    assert not result.passed
    assert len(result.disagreements) == 2
