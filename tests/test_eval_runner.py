from __future__ import annotations

from argus.eval.dataset import GoldenItem, Thresholds
from argus.eval.judge import Verdict
from argus.eval.runner import evaluate
from argus.rag.retriever import RetrievedChunk


def _hit_chunk(source: str = "x/a.md", content: str = "KEDA scales the pods") -> RetrievedChunk:
    return RetrievedChunk(content=content, source_uri=source, score=1.0)


async def test_passes_when_retrieval_answer_and_judge_are_all_good() -> None:
    golden = [GoldenItem(question="q1", relevant_sources=["a.md"], must_include=["KEDA"])]
    thresholds = Thresholds(
        k=5, min_hit_at_k=1.0, min_precision_at_k=0.1, min_mrr=1.0, min_judge_pass_rate=1.0
    )

    async def retrieve(question: str) -> list[RetrievedChunk]:
        return [_hit_chunk()]

    async def answer(question: str) -> str:
        return "It uses KEDA to scale searcher pods from zero."

    async def judge(question: str, answer_text: str, context: str) -> Verdict:
        return Verdict(passed=True, reason="ok")

    report = await evaluate(golden, thresholds, retrieve=retrieve, answer=answer, judge=judge)
    assert report.passed
    assert report.hit_at_k == 1.0
    assert report.mrr == 1.0
    assert report.judge_pass_rate == 1.0


async def test_judge_and_keyword_signals_are_independent() -> None:
    golden = [GoldenItem(question="q1", relevant_sources=["a.md"], must_include=["KEDA"])]
    thresholds = Thresholds(
        min_hit_at_k=0.0,
        min_precision_at_k=0.0,
        min_mrr=0.0,
        min_judge_pass_rate=1.0,
        min_keyword_pass_rate=1.0,
    )

    async def retrieve(question: str) -> list[RetrievedChunk]:
        return [_hit_chunk()]

    async def answer(question: str) -> str:
        return "It scales somehow."  # judge passes, but the keyword is absent

    async def judge(question: str, answer_text: str, context: str) -> Verdict:
        return Verdict(passed=True, reason="ok")

    report = await evaluate(golden, thresholds, retrieve=retrieve, answer=answer, judge=judge)
    assert not report.passed
    assert report.judge_pass_rate == 1.0  # the judge is not dragged down by a phrasing miss
    assert report.keyword_pass_rate == 0.0
    assert any("keyword_pass_rate" in failure for failure in report.failures)


async def test_keyword_check_is_punctuation_insensitive() -> None:
    golden = [
        GoldenItem(question="q1", relevant_sources=["a.md"], must_include=["nomic-embed-text"])
    ]
    thresholds = Thresholds(
        min_hit_at_k=0.0, min_precision_at_k=0.0, min_mrr=0.0, min_judge_pass_rate=0.0
    )

    async def retrieve(question: str) -> list[RetrievedChunk]:
        return [_hit_chunk()]

    async def answer(question: str) -> str:
        return "Argus embeds with the nomic embed text model."  # spaces, not hyphens

    async def judge(question: str, answer_text: str, context: str) -> Verdict:
        return Verdict(passed=True, reason="ok")

    report = await evaluate(golden, thresholds, retrieve=retrieve, answer=answer, judge=judge)
    assert report.keyword_pass_rate == 1.0


async def test_retrieval_miss_fails_the_gate() -> None:
    golden = [GoldenItem(question="q1", relevant_sources=["a.md"])]
    thresholds = Thresholds(
        min_hit_at_k=1.0, min_precision_at_k=0.0, min_mrr=0.0, min_judge_pass_rate=0.0
    )

    async def retrieve(question: str) -> list[RetrievedChunk]:
        return [_hit_chunk(source="x/b.md")]

    async def answer(question: str) -> str:
        return "whatever"

    async def judge(question: str, answer_text: str, context: str) -> Verdict:
        return Verdict(passed=True, reason="ok")

    report = await evaluate(golden, thresholds, retrieve=retrieve, answer=answer, judge=judge)
    assert not report.passed
    assert report.hit_at_k == 0.0
    assert any("hit@" in failure for failure in report.failures)
