"""Judge calibration: does the LLM judge agree with human labels?

An LLM judge that gates a build is only trustworthy if it agrees with humans on
cases where the answer is known to be right or wrong. This runs the judge over a
human-labelled set and reports Cohen's kappa — chance-corrected agreement — so a
judge that just rubber-stamps everything is exposed (its kappa collapses).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from argus.eval.dataset import CalibrationItem
from argus.eval.judge import Verdict
from argus.eval.metrics import cohen_kappa, mean
from argus.logging import get_logger

log = get_logger(__name__)

JudgeFn = Callable[[str, str, str], Awaitable[Verdict]]


@dataclass(frozen=True)
class CalibrationResult:
    n: int
    kappa: float
    agreement: float
    passed: bool
    disagreements: list[str]


async def calibrate(
    items: list[CalibrationItem], *, judge: JudgeFn, min_kappa: float
) -> CalibrationResult:
    human: list[str] = [item.label for item in items]
    machine: list[str] = []
    disagreements: list[str] = []
    for item in items:
        verdict: Verdict = await judge(item.question, item.answer, item.context)
        label: str = "pass" if verdict.passed else "fail"
        machine.append(label)
        if label != item.label:
            disagreements.append(f"{item.question[:60]} — human={item.label} judge={label}")

    kappa: float = cohen_kappa(human, machine)
    agreement: float = mean([1.0 if h == m else 0.0 for h, m in zip(human, machine, strict=True)])
    log.info("judge_calibration", n=len(items), kappa=kappa, agreement=agreement)
    return CalibrationResult(
        n=len(items),
        kappa=kappa,
        agreement=agreement,
        passed=kappa >= min_kappa,
        disagreements=disagreements,
    )
