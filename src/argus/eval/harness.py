"""Wire the real retriever, agent loop, and judge into the eval runner.

This is the live gate: it ingests the eval corpus (the repo's own docs) into a
dedicated corpus, then runs the golden set through real retrieval, a real agent
answer, and the LLM judge. Needs the data stack and an LLM, so it runs from
`argus eval` / `make eval`, not in hermetic CI.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import orjson

from argus.agent.budget import Budget
from argus.agent.loop import AgentLoop
from argus.agent.prompts import research_system_prompt
from argus.builders import build_llm
from argus.config import get_settings
from argus.db import close_pool
from argus.eval.calibration import CalibrationResult, calibrate
from argus.eval.dataset import load_calibration, load_golden, load_thresholds
from argus.eval.judge import Verdict, judge_answer
from argus.eval.runner import EvalReport, evaluate
from argus.logging import get_logger
from argus.rag.ingest import ingest_source
from argus.rag.retriever import RetrievedChunk, retrieve
from argus.tools.rag_search import register_rag_search
from argus.tools.registry import ToolRegistry
from argus.tools.web_fetch import register_web_fetch
from argus.tools.web_search import register_web_search

log = get_logger(__name__)

_CORPUS: str = "argus-eval"
# A curated, source-grounded knowledge corpus on RAG & vector search (eval/corpus/),
# authored from authoritative references. The golden set's questions are answerable
# from these docs; negatives deliberately fall outside them. See eval/corpus/README.md.
_SOURCES: tuple[str, ...] = (
    "eval/corpus/01_embeddings.md",
    "eval/corpus/02_ann_and_vector_databases.md",
    "eval/corpus/03_hnsw.md",
    "eval/corpus/04_ivf_and_quantization.md",
    "eval/corpus/05_lexical_bm25.md",
    "eval/corpus/06_hybrid_search_rrf.md",
    "eval/corpus/07_rerankers.md",
    "eval/corpus/08_chunking_contextual_retrieval.md",
    "eval/corpus/09_rag_architecture_and_evaluation.md",
)


async def run_gate(golden_path: Path, thresholds_path: Path, report_path: Path) -> EvalReport:
    settings = get_settings()
    golden = load_golden(golden_path)
    thresholds = load_thresholds(thresholds_path)

    llm = build_llm(settings)
    judge_llm = build_llm(settings, model=settings.judge_model, temperature=0.0)
    registry = ToolRegistry()
    register_web_search(registry)
    register_web_fetch(registry)
    register_rag_search(registry, corpus=_CORPUS)
    budget = Budget(
        max_turns=settings.max_turns,
        max_tokens=settings.max_tokens,
        max_wallclock_s=settings.max_wallclock_s,
        max_cost_usd=settings.max_cost_usd,
    )

    async def _retrieve(question: str) -> list[RetrievedChunk]:
        return await retrieve(question, top_k=thresholds.k, corpus=_CORPUS)

    async def _answer(question: str) -> str:
        loop = AgentLoop(
            registry=registry, llm=llm, budget=budget, system_prompt=research_system_prompt()
        )
        result = await loop.run(question)
        return result.answer

    async def _judge(question: str, answer: str, context: str) -> Verdict:
        return await judge_answer(judge_llm, question=question, answer=answer, context=context)

    log.info("eval_start", golden=len(golden), sources=len(_SOURCES), model=settings.model)
    try:
        for source in _SOURCES:
            log.info("eval_ingest", source=source)  # contextualize+embed is slow on a local LLM
            await ingest_source(source, corpus=_CORPUS)
        report = await evaluate(
            golden, thresholds, retrieve=_retrieve, answer=_answer, judge=_judge
        )
    finally:
        await close_pool()

    data: bytes = orjson.dumps(_report_dict(report), option=orjson.OPT_INDENT_2)
    await asyncio.to_thread(report_path.write_bytes, data)
    log.info("eval_done", passed=report.passed, n=report.n, failures=report.failures)
    return report


async def run_calibration(calibration_path: Path, thresholds_path: Path) -> CalibrationResult:
    settings = get_settings()
    items = load_calibration(calibration_path)
    thresholds = load_thresholds(thresholds_path)
    judge_llm = build_llm(settings, model=settings.judge_model, temperature=0.0)

    async def _judge(question: str, answer: str, context: str) -> Verdict:
        return await judge_answer(judge_llm, question=question, answer=answer, context=context)

    return await calibrate(items, judge=_judge, min_kappa=thresholds.min_judge_kappa)


def _report_dict(report: EvalReport) -> dict[str, Any]:
    return {
        "n": report.n,
        "n_unanswerable": report.n_unanswerable,
        "hit_at_k": report.hit_at_k,
        "precision_at_k": report.precision_at_k,
        "mrr": report.mrr,
        "judge_pass_rate": report.judge_pass_rate,
        "keyword_pass_rate": report.keyword_pass_rate,
        "context_precision": report.context_precision,
        "context_recall": report.context_recall,
        "faithfulness": report.faithfulness,
        "answer_relevancy": report.answer_relevancy,
        "abstention_rate": report.abstention_rate,
        "passed": report.passed,
        "failures": report.failures,
        "items": [
            {
                "question": item.question,
                "answer": item.answer,
                "hit": item.hit,
                "precision": item.precision,
                "reciprocal_rank": item.reciprocal_rank,
                "judge_passed": item.judge_passed,
                "judge_reason": item.judge_reason,
                "keyword_ok": item.keyword_ok,
                "faithful": item.faithful,
                "relevant": item.relevant,
                "unanswerable": item.unanswerable,
                "abstained": item.abstained,
            }
            for item in report.items
        ],
    }
