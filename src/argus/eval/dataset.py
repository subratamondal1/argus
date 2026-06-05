"""Golden dataset and threshold loading for the eval gate."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import orjson
from pydantic import BaseModel, Field


class GoldenItem(BaseModel):
    question: str = Field(description="The question to ask Argus.")
    relevant_sources: list[str] = Field(
        default_factory=list,
        description="Source-uri substrings that count as a relevant retrieval; empty when unanswerable.",
    )
    must_include: list[str] = Field(
        default_factory=list,
        description="Substrings the answer must contain (cheap grounding check).",
    )
    unanswerable: bool = Field(
        default=False,
        description=(
            "A negative case: the corpus cannot answer this, so a faithful system must "
            "abstain. Excluded from retrieval/judge metrics; scored by abstention_rate."
        ),
    )


class CalibrationItem(BaseModel):
    question: str
    answer: str
    context: str
    label: Literal["pass", "fail"] = Field(description="The human verdict for this answer.")


class Thresholds(BaseModel):
    k: int = Field(default=5, gt=0)
    min_hit_at_k: float = 0.8
    min_precision_at_k: float = 0.2
    min_mrr: float = 0.6
    min_judge_pass_rate: float = 0.7
    min_keyword_pass_rate: float = 0.6
    min_faithfulness: float = 0.7  # RAGAS faithfulness: answers grounded, not hallucinated
    min_abstention_rate: float = 0.7  # negatives correctly declined ("insufficient information")
    min_judge_kappa: float = 0.6
    # Permissive default so ad-hoc/test threshold sets don't trip the guard; the
    # production floor lives in eval/thresholds.json.
    min_cases: int = Field(default=1, gt=0)


def load_golden(path: Path) -> list[GoldenItem]:
    items: list[GoldenItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped: str = line.strip()
        if stripped:
            items.append(GoldenItem.model_validate(orjson.loads(stripped)))
    return items


def load_thresholds(path: Path) -> Thresholds:
    return Thresholds.model_validate(orjson.loads(path.read_text(encoding="utf-8")))


def load_calibration(path: Path) -> list[CalibrationItem]:
    items: list[CalibrationItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped: str = line.strip()
        if stripped:
            items.append(CalibrationItem.model_validate(orjson.loads(stripped)))
    return items
