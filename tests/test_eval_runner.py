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


async def test_too_few_cases_fails_the_gate_without_crashing() -> None:
    golden = [GoldenItem(question="q1", relevant_sources=["a.md"])]
    thresholds = Thresholds(min_cases=6)  # one case, floor of six

    async def retrieve(question: str) -> list[RetrievedChunk]:
        return [_hit_chunk()]

    async def answer(question: str) -> str:
        return "whatever"

    async def judge(question: str, answer_text: str, context: str) -> Verdict:
        return Verdict(passed=True, reason="ok")

    report = await evaluate(golden, thresholds, retrieve=retrieve, answer=answer, judge=judge)
    assert not report.passed
    assert report.n == 1
    assert any("too few eval cases" in failure for failure in report.failures)


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


def _permissive() -> Thresholds:
    return Thresholds(
        min_hit_at_k=0.0,
        min_precision_at_k=0.0,
        min_mrr=0.0,
        min_judge_pass_rate=0.0,
        min_keyword_pass_rate=0.0,
        min_faithfulness=0.0,
        min_cases=1,
    )


async def test_ragas_named_metrics_are_reported() -> None:
    golden = [GoldenItem(question="q1", relevant_sources=["a.md"], must_include=["KEDA"])]

    async def retrieve(question: str) -> list[RetrievedChunk]:
        return [_hit_chunk()]

    async def answer(question: str) -> str:
        return "It uses KEDA to scale searcher pods from zero."

    async def judge(question: str, answer_text: str, context: str) -> Verdict:
        return Verdict(passed=True, faithful=True, relevant=True, reason="ok")

    report = await evaluate(golden, _permissive(), retrieve=retrieve, answer=answer, judge=judge)
    assert report.context_precision == report.precision_at_k  # RAGAS alias of precision@k
    assert report.context_recall == report.hit_at_k  # RAGAS alias of hit@k
    assert report.faithfulness == 1.0
    assert report.answer_relevancy == 1.0


async def test_unanswerable_item_scored_by_abstention_not_retrieval() -> None:
    golden = [
        GoldenItem(question="answerable", relevant_sources=["a.md"], must_include=["KEDA"]),
        GoldenItem(question="off-topic", unanswerable=True),
    ]

    async def retrieve(question: str) -> list[RetrievedChunk]:
        return [_hit_chunk()]  # an irrelevant chunk is still retrieved for the negative

    async def answer(question: str) -> str:
        # The system correctly declines the unanswerable one.
        return "KEDA scales the pods." if question == "answerable" else "That's not in the corpus."

    async def judge(question: str, answer_text: str, context: str) -> Verdict:
        return Verdict(passed=True, reason="ok")

    report = await evaluate(golden, _permissive(), retrieve=retrieve, answer=answer, judge=judge)
    assert report.n == 2
    assert report.n_unanswerable == 1
    assert report.hit_at_k == 1.0  # computed over the 1 answerable item only, not dragged to 0.5
    assert report.abstention_rate == 1.0  # the negative was correctly declined
    assert report.passed


async def test_hallucinating_on_a_negative_fails_the_gate() -> None:
    golden = [GoldenItem(question="off-topic", unanswerable=True)]
    thresholds = Thresholds(min_cases=1, min_abstention_rate=0.7)

    async def retrieve(question: str) -> list[RetrievedChunk]:
        return [_hit_chunk()]

    async def answer(question: str) -> str:
        return "Sure! The answer is 42 teraflops of attention heads."  # confident hallucination

    async def judge(question: str, answer_text: str, context: str) -> Verdict:
        return Verdict(passed=True, reason="ok")

    report = await evaluate(golden, thresholds, retrieve=retrieve, answer=answer, judge=judge)
    assert not report.passed
    assert report.abstention_rate == 0.0
    assert any("abstention_rate" in failure for failure in report.failures)
