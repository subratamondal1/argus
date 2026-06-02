"""Run the golden set through injected retrieve/answer/judge, then aggregate.

The runner is pure orchestration over three injected callables, so its
pass/fail logic is unit-tested in CI with fakes — no DB, no LLM. harness.py
wires the real retriever, agent loop, and judge.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from argus.eval.dataset import GoldenItem, Thresholds
from argus.eval.judge import Verdict
from argus.eval.metrics import hit_at_k, mean, precision_at_k, reciprocal_rank
from argus.logging import get_logger
from argus.rag.retriever import RetrievedChunk

log = get_logger(__name__)

RetrieveFn = Callable[[str], Awaitable[list[RetrievedChunk]]]
AnswerFn = Callable[[str], Awaitable[str]]
JudgeFn = Callable[[str, str, str], Awaitable[Verdict]]


@dataclass(frozen=True)
class ItemResult:
    question: str
    hit: float
    precision: float
    reciprocal_rank: float
    judge_passed: bool
    keyword_ok: bool


@dataclass(frozen=True)
class EvalReport:
    n: int
    hit_at_k: float
    precision_at_k: float
    mrr: float
    judge_pass_rate: float
    passed: bool
    failures: list[str]
    items: list[ItemResult]


def _is_relevant(source_uri: str, patterns: list[str]) -> bool:
    return any(pattern in source_uri for pattern in patterns)


async def evaluate(
    golden: list[GoldenItem],
    thresholds: Thresholds,
    *,
    retrieve: RetrieveFn,
    answer: AnswerFn,
    judge: JudgeFn,
) -> EvalReport:
    results: list[ItemResult] = []
    for item in golden:
        chunks: list[RetrievedChunk] = await retrieve(item.question)
        relevances: list[bool] = [
            _is_relevant(chunk.source_uri, item.relevant_sources) for chunk in chunks
        ]
        answer_text: str = await answer(item.question)
        context: str = "\n\n".join(chunk.content for chunk in chunks)
        verdict: Verdict = await judge(item.question, answer_text, context)
        keyword_ok: bool = all(
            keyword.lower() in answer_text.lower() for keyword in item.must_include
        )
        results.append(
            ItemResult(
                question=item.question,
                hit=hit_at_k(relevances, thresholds.k),
                precision=precision_at_k(relevances, thresholds.k),
                reciprocal_rank=reciprocal_rank(relevances),
                judge_passed=verdict.passed,
                keyword_ok=keyword_ok,
            )
        )
        log.info("eval_item", question=item.question, hit=results[-1].hit, judged=verdict.passed)
    return _aggregate(results, thresholds)


def _aggregate(results: list[ItemResult], thresholds: Thresholds) -> EvalReport:
    hit: float = mean([result.hit for result in results])
    precision: float = mean([result.precision for result in results])
    mrr: float = mean([result.reciprocal_rank for result in results])
    judge_pass_rate: float = mean(
        [1.0 if (result.judge_passed and result.keyword_ok) else 0.0 for result in results]
    )

    failures: list[str] = []
    if hit < thresholds.min_hit_at_k:
        failures.append(f"hit@{thresholds.k} {hit:.3f} < {thresholds.min_hit_at_k}")
    if precision < thresholds.min_precision_at_k:
        failures.append(
            f"precision@{thresholds.k} {precision:.3f} < {thresholds.min_precision_at_k}"
        )
    if mrr < thresholds.min_mrr:
        failures.append(f"mrr {mrr:.3f} < {thresholds.min_mrr}")
    if judge_pass_rate < thresholds.min_judge_pass_rate:
        failures.append(f"judge_pass_rate {judge_pass_rate:.3f} < {thresholds.min_judge_pass_rate}")

    return EvalReport(
        n=len(results),
        hit_at_k=hit,
        precision_at_k=precision,
        mrr=mrr,
        judge_pass_rate=judge_pass_rate,
        passed=not failures,
        failures=failures,
        items=results,
    )
