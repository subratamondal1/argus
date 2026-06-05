"""Run the golden set through injected retrieve/answer/judge, then aggregate.

The runner is pure orchestration over three injected callables, so its
pass/fail logic is unit-tested in CI with fakes — no DB, no LLM. harness.py
wires the real retriever, agent loop, and judge.

Two answer-quality signals are kept separate: the LLM judge (semantic
correctness + grounding) and a normalized keyword check (a cheap, deterministic
grounding guard). They are reported and gated independently so a phrasing
difference never masquerades as a wrong answer.
"""

from __future__ import annotations

import re
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

_ANSWER_PREVIEW_CHARS: int = 400


@dataclass(frozen=True)
class ItemResult:
    question: str
    answer: str
    hit: float
    precision: float
    reciprocal_rank: float
    judge_passed: bool
    judge_reason: str
    keyword_ok: bool
    faithful: bool = True
    relevant: bool = True
    unanswerable: bool = False
    abstained: bool = False


@dataclass(frozen=True)
class EvalReport:
    n: int
    hit_at_k: float
    precision_at_k: float
    mrr: float
    judge_pass_rate: float
    keyword_pass_rate: float
    passed: bool
    failures: list[str]
    items: list[ItemResult]
    # RAGAS-vocabulary view (retrieval/generation computed over answerable items):
    # context_precision == precision@k, context_recall == hit@k, plus faithfulness
    # (grounded, no hallucination) and answer_relevancy (addresses the question).
    context_precision: float = 0.0
    context_recall: float = 0.0
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    # Negative cases: fraction of unanswerable items the system correctly declined.
    abstention_rate: float = 1.0
    n_unanswerable: int = 0


# Phrases that signal a faithful "I can't answer that from the corpus" abstention,
# which is the correct behaviour on a negative/unanswerable item.
_ABSTENTION_MARKERS: tuple[str, ...] = (
    "insufficient",
    "don't have",
    "do not have",
    "not in the",
    "no information",
    "cannot answer",
    "can't answer",
    "unable to",
    "not provided",
    "not contain",
    "not enough",
    "i don't know",
    "not available",
    "no relevant",
    "not mentioned",
    "not covered",
    "doesn't mention",
    "does not mention",
)


def _is_abstention(answer: str) -> bool:
    lowered: str = answer.lower()
    return any(marker in lowered for marker in _ABSTENTION_MARKERS)


def _is_relevant(source_uri: str, patterns: list[str]) -> bool:
    return any(pattern in source_uri for pattern in patterns)


def _normalize(text: str) -> str:
    return re.sub(r"[\s_-]+", " ", text.lower()).strip()


_KEYWORD_COVERAGE_FLOOR: float = 0.6


def _keyword_ok(answer: str, must_include: list[str]) -> bool:
    # A grounding guard, not a phrasing trap: a correct answer phrases things its own
    # way, so require a MAJORITY of the expected substrings rather than every one. The
    # LLM judge carries correctness; this is the cheap deterministic backstop.
    if not must_include:
        return True
    normalized: str = _normalize(answer)
    present: int = sum(1 for keyword in must_include if _normalize(keyword) in normalized)
    return present / len(must_include) >= _KEYWORD_COVERAGE_FLOOR


async def evaluate(
    golden: list[GoldenItem],
    thresholds: Thresholds,
    *,
    retrieve: RetrieveFn,
    answer: AnswerFn,
    judge: JudgeFn,
) -> EvalReport:
    results: list[ItemResult] = []
    total: int = len(golden)
    log.info("eval_run", n=total)
    for index, item in enumerate(golden, start=1):
        # Log BEFORE the slow retrieve+answer+judge so progress is visible per item
        # (on a local LLM each item can take seconds, which otherwise looks hung).
        log.info("eval_item_start", i=index, n=total, question=item.question)
        answer_text: str = await answer(item.question)

        if item.unanswerable:
            # The corpus can't answer this; the only correct behaviour is to abstain.
            # Retrieval/judge metrics don't apply, so it's scored solely on abstention.
            abstained: bool = _is_abstention(answer_text)
            results.append(
                ItemResult(
                    question=item.question,
                    answer=answer_text[:_ANSWER_PREVIEW_CHARS],
                    hit=0.0,
                    precision=0.0,
                    reciprocal_rank=0.0,
                    judge_passed=abstained,
                    judge_reason="abstained" if abstained else "hallucinated on a negative case",
                    keyword_ok=False,
                    faithful=abstained,
                    relevant=False,
                    unanswerable=True,
                    abstained=abstained,
                )
            )
            log.info("eval_item", i=index, n=total, question=item.question, abstained=abstained)
            continue

        chunks: list[RetrievedChunk] = await retrieve(item.question)
        relevances: list[bool] = [
            _is_relevant(chunk.source_uri, item.relevant_sources) for chunk in chunks
        ]
        context: str = "\n\n".join(chunk.content for chunk in chunks)
        verdict: Verdict = await judge(item.question, answer_text, context)
        results.append(
            ItemResult(
                question=item.question,
                answer=answer_text[:_ANSWER_PREVIEW_CHARS],
                hit=hit_at_k(relevances, thresholds.k),
                precision=precision_at_k(relevances, thresholds.k),
                reciprocal_rank=reciprocal_rank(relevances),
                judge_passed=verdict.passed,
                judge_reason=verdict.reason,
                keyword_ok=_keyword_ok(answer_text, item.must_include),
                faithful=verdict.faithful,
                relevant=verdict.relevant,
            )
        )
        log.info(
            "eval_item",
            i=index,
            n=total,
            question=item.question,
            hit=results[-1].hit,
            judged=verdict.passed,
        )
    return _aggregate(results, thresholds)


def _aggregate(results: list[ItemResult], thresholds: Thresholds) -> EvalReport:
    # Guard a too-small (or empty) golden set: a 2-case gate that "passes" is
    # noise, and mean([]) would raise. Fail closed and say so.
    if len(results) < thresholds.min_cases:
        return EvalReport(
            n=len(results),
            hit_at_k=0.0,
            precision_at_k=0.0,
            mrr=0.0,
            judge_pass_rate=0.0,
            keyword_pass_rate=0.0,
            passed=False,
            failures=[
                f"too few eval cases: {len(results)} < min_cases {thresholds.min_cases} "
                "(grow the golden set)"
            ],
            items=results,
        )

    # Retrieval + generation metrics are computed over ANSWERABLE items only;
    # negatives (relevant_sources == [], unanswerable) are scored by abstention so a
    # correct "I can't answer that" isn't punished as a retrieval miss.
    answerable: list[ItemResult] = [r for r in results if not r.unanswerable]
    unanswerable: list[ItemResult] = [r for r in results if r.unanswerable]

    hit: float = mean([result.hit for result in answerable])
    precision: float = mean([result.precision for result in answerable])
    mrr: float = mean([result.reciprocal_rank for result in answerable])
    judge_pass_rate: float = mean([1.0 if result.judge_passed else 0.0 for result in answerable])
    keyword_pass_rate: float = mean([1.0 if result.keyword_ok else 0.0 for result in answerable])
    faithfulness: float = mean([1.0 if result.faithful else 0.0 for result in answerable])
    answer_relevancy: float = mean([1.0 if result.relevant else 0.0 for result in answerable])
    # 1.0 when there are no negatives, so a set without them neither helps nor hurts.
    abstention_rate: float = (
        mean([1.0 if result.abstained else 0.0 for result in unanswerable]) if unanswerable else 1.0
    )

    failures: list[str] = []
    if answerable:
        if hit < thresholds.min_hit_at_k:
            failures.append(f"hit@{thresholds.k} {hit:.3f} < {thresholds.min_hit_at_k}")
        if precision < thresholds.min_precision_at_k:
            failures.append(
                f"precision@{thresholds.k} {precision:.3f} < {thresholds.min_precision_at_k}"
            )
        if mrr < thresholds.min_mrr:
            failures.append(f"mrr {mrr:.3f} < {thresholds.min_mrr}")
        if judge_pass_rate < thresholds.min_judge_pass_rate:
            failures.append(
                f"judge_pass_rate {judge_pass_rate:.3f} < {thresholds.min_judge_pass_rate}"
            )
        if keyword_pass_rate < thresholds.min_keyword_pass_rate:
            failures.append(
                f"keyword_pass_rate {keyword_pass_rate:.3f} < {thresholds.min_keyword_pass_rate}"
            )
        if faithfulness < thresholds.min_faithfulness:
            failures.append(f"faithfulness {faithfulness:.3f} < {thresholds.min_faithfulness}")
    if unanswerable and abstention_rate < thresholds.min_abstention_rate:
        failures.append(f"abstention_rate {abstention_rate:.3f} < {thresholds.min_abstention_rate}")

    return EvalReport(
        n=len(results),
        hit_at_k=hit,
        precision_at_k=precision,
        mrr=mrr,
        judge_pass_rate=judge_pass_rate,
        keyword_pass_rate=keyword_pass_rate,
        passed=not failures,
        failures=failures,
        items=results,
        context_precision=precision,
        context_recall=hit,
        faithfulness=faithfulness,
        answer_relevancy=answer_relevancy,
        abstention_rate=abstention_rate,
        n_unanswerable=len(unanswerable),
    )
